from __future__ import annotations

import abc
import asyncio
import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Callable, TypeVar

if TYPE_CHECKING:
    from robusta_krr.core.abstract.strategies import ResourceHistoryData
    from robusta_krr.core.models.objects import K8sObjectData

    from ..loader import CustomPrometheusConnect

REGISTERED_METRICS: dict[str, type[BaseMetricLoader]] = {}


class BaseMetricLoader(abc.ABC):
    def __init__(self, prometheus: CustomPrometheusConnect) -> None:
        self.prometheus = prometheus

    @abc.abstractmethod
    def get_query(self, namespace: str, pod: str, container: str) -> str:
        ...

    async def load_data(self, object: K8sObjectData, period: datetime.timedelta, step: str) -> ResourceHistoryData:
        result = await asyncio.gather(
            *[
                asyncio.to_thread(
                    self.prometheus.custom_query_range,
                    query=self.get_query(object.namespace, pod, object.container),
                    start_time=datetime.datetime.now() - period,
                    end_time=datetime.datetime.now(),
                    step=step,
                )
                for pod in object.pods
            ]
        )

        if result == []:
            return {pod: [] for pod in object.pods}

        pod_results = {pod: result[i] for i, pod in enumerate(object.pods)}
        return {
            pod: [Decimal(value) for _, value in pod_result[0]["values"]]
            for pod, pod_result in pod_results.items()
            if pod_result != []
        }

    @staticmethod
    def get_by_resource(resource: str) -> type[BaseMetricLoader]:
        try:
            return REGISTERED_METRICS[resource]
        except KeyError as e:
            raise KeyError(f"Resource {resource} was not registered by `@bind_metric(...)`") from e


Self = TypeVar("Self", bound=BaseMetricLoader)


def bind_metric(resource: str) -> Callable[[type[Self]], type[Self]]:
    def decorator(cls: type[Self]) -> type[Self]:
        REGISTERED_METRICS[resource] = cls
        return cls

    return decorator
