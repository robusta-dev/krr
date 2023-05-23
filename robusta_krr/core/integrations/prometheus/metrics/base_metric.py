from __future__ import annotations

import abc
import asyncio
import datetime
from typing import TYPE_CHECKING, Callable, TypeVar

from robusta_krr.core.abstract.strategies import ResourceHistoryData
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.utils.configurable import Configurable

import numpy as np

if TYPE_CHECKING:
    from ..loader import CustomPrometheusConnect

REGISTERED_METRICS: dict[str, type[BaseMetricLoader]] = {}


class BaseMetricLoader(Configurable, abc.ABC):
    def __init__(self, config: Config, prometheus: CustomPrometheusConnect) -> None:
        super().__init__(config)
        self.prometheus = prometheus

    @abc.abstractmethod
    def get_query(self, object: K8sObjectData) -> str:
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
        query = self.get_query(object)
        result = await self.query_prometheus(
            query=query,
            start_time=datetime.datetime.now() - period,
            end_time=datetime.datetime.now(),
            step=step,
        )

        if result == []:
            self.warning(f"Prometheus returned no {self.__class__.__name__} metrics for {object}")
            return ResourceHistoryData(query=query, data={})

        return ResourceHistoryData(
            query=query,
            data={
                pod_result['metric']['pod']: np.array(pod_result["values"], dtype=np.float64)
                for pod_result in result
            },
        )

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
