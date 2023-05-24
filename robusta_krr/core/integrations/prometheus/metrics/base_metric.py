from __future__ import annotations

import abc
import asyncio
import datetime
from typing import TYPE_CHECKING, Callable, TypeVar

import numpy as np

from robusta_krr.core.abstract.strategies import Metric, ResourceHistoryData
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
    def get_query(self, object: K8sObjectData) -> str:
        ...

    def _step_to_string(self, step: datetime.timedelta) -> str:
        return f"{int(step.total_seconds()) // 60}m"

    async def query_prometheus(self, metric: Metric) -> list[dict]:
        return await asyncio.to_thread(
            self.prometheus.custom_query_range,
            query=metric.query,
            start_time=metric.start_time,
            end_time=metric.end_time,
            step=metric.step,
        )

    async def load_data(
        self, object: K8sObjectData, period: datetime.timedelta, step: datetime.timedelta
    ) -> ResourceHistoryData:
        query = self.get_query(object)
        end_time = datetime.datetime.now()
        metric = Metric(
            query=query,
            start_time=end_time - period,
            end_time=end_time,
            step=self._step_to_string(step),
        )
        result = await self.query_prometheus(metric)

        if result == []:
            self.warning(f"Prometheus returned no {self.__class__.__name__} metrics for {object}")
            return ResourceHistoryData(metric=metric, data={})

        return ResourceHistoryData(
            metric=metric,
            data={
                pod_result["metric"]["pod"]: np.array(pod_result["values"], dtype=np.float64) for pod_result in result
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
