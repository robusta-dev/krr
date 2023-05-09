from __future__ import annotations

import abc
import asyncio
import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Callable, TypeVar

from robusta_krr.core.abstract.strategies import ResourceHistoryData
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.utils.configurable import Configurable

if TYPE_CHECKING:
    from ..loader import CustomPrometheusConnect

REGISTERED_METRICS: dict[str, type[BaseMetricLoader]] = {}


class BaseMetricLoader(Configurable, abc.ABC):
    def __init__(self, config: Config, prometheus: CustomPrometheusConnect) -> None:
        super().__init__(config)
        self.prometheus = prometheus

    @abc.abstractmethod
    def get_query(self, namespace: str, pod: str, container: str) -> str:
        ...

    async def query_prometheus(
        self, query: str, start_time: datetime.datetime, end_time: datetime.datetime, step: datetime.timedelta
    ) -> list[dict]:
        return await asyncio.to_thread(
            self.prometheus.custom_query_range,
            query=query,
            start_time=start_time,
            end_time=end_time,
            step=f"{int(step.total_seconds()) // 60}m",
        )

    async def load_data(
        self, object: K8sObjectData, period: datetime.timedelta, step: datetime.timedelta
    ) -> ResourceHistoryData:
        result = await asyncio.gather(
            *[
                self.query_prometheus(
                    query=self.get_query(object.namespace, pod.name, object.container),
                    start_time=datetime.datetime.now() - period,
                    end_time=datetime.datetime.now(),
                    step=step,
                )
                for pod in object.pods
            ]
        )

        if result == []:
            self.warning(f"Prometheus returned no {self.__class__.__name__} metrics for {object}")
            return {pod.name: [] for pod in object.pods}

        pod_results = {pod: result[i] for i, pod in enumerate(object.pods)}
        return {
            pod.name: [Decimal(value) for _, value in pod_result[0]["values"]]
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
