from __future__ import annotations

import abc
import asyncio
from concurrent.futures import ThreadPoolExecutor
import datetime
from typing import TYPE_CHECKING, Callable, Optional, TypeVar

import numpy as np

from robusta_krr.core.abstract.strategies import Metric, ResourceHistoryData
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.utils.configurable import Configurable

if TYPE_CHECKING:
    from .. import CustomPrometheusConnect

# A registry of metrics that can be used to fetch a corresponding metric loader.
REGISTERED_METRICS: dict[str, type[BaseMetricLoader]] = {}


class BaseMetricLoader(Configurable, abc.ABC):
    """
    Base class for all metric loaders.

    Metric loaders are used to load metrics from a specified source (like Prometheus in this case).
    """

    def __init__(
        self,
        config: Config,
        prometheus: CustomPrometheusConnect,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        super().__init__(config)
        self.prometheus = prometheus

        self.executor = executor

    def get_prometheus_cluster_label(self) -> str:
        """
        Generates the cluster label for querying a centralized Prometheus

        Returns:
        str: a promql safe label string for querying the cluster.
        """
        if self.config.prometheus_cluster_label is None:
            return ""
        return f', {self.config.prometheus_label}="{self.config.prometheus_cluster_label}"'

    @abc.abstractmethod
    def get_query(self, object: K8sObjectData) -> str:
        """
        This method should be implemented by all subclasses to provide a query string to fetch metrics.

        Args:
        object (K8sObjectData): The object for which metrics need to be fetched.

        Returns:
        str: The query string.
        """

        pass

    def _step_to_string(self, step: datetime.timedelta) -> str:
        """
        Converts step in datetime.timedelta format to a string format used by Prometheus.

        Args:
        step (datetime.timedelta): Step size in datetime.timedelta format.

        Returns:
        str: Step size in string format used by Prometheus.
        """

        return f"{int(step.total_seconds()) // 60}m"

    async def query_prometheus(self, metric: Metric) -> list[dict]:
        """
        Asynchronous method that queries Prometheus to fetch metrics.

        Args:
        metric (Metric): An instance of the Metric class specifying what metrics to fetch.

        Returns:
        list[dict]: A list of dictionary where each dictionary represents metrics for a pod.
        """

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: self.prometheus.custom_query_range(
                query=metric.query,
                start_time=metric.start_time,
                end_time=metric.end_time,
                step=metric.step,
            ),
        )

    async def load_data(
        self, object: K8sObjectData, period: datetime.timedelta, step: datetime.timedelta, service_name: str
    ) -> ResourceHistoryData:
        """
        Asynchronous method that loads metric data for a specific object.

        Args:
        object (K8sObjectData): The object for which metrics need to be loaded.
        period (datetime.timedelta): The time period for which metrics need to be loaded.
        step (datetime.timedelta): The time interval between successive metric values.

        Returns:
        ResourceHistoryData: An instance of the ResourceHistoryData class representing the loaded metrics.
        """

        query = self.get_query(object)
        end_time = datetime.datetime.now().astimezone()
        metric = Metric(
            query=query,
            start_time=end_time - period,
            end_time=end_time,
            step=self._step_to_string(step),
        )
        result = await self.query_prometheus(metric)

        if result == []:
            self.warning(f"{service_name} returned no {self.__class__.__name__} metrics for {object}")
            return ResourceHistoryData(metric=metric, data={})

        return ResourceHistoryData(
            metric=metric,
            data={
                pod_result["metric"]["pod"]: np.array(pod_result["values"], dtype=np.float64) for pod_result in result
            },
        )

    @staticmethod
    def get_by_resource(resource: str) -> type[BaseMetricLoader]:
        """
        Fetches the metric loader corresponding to the specified resource.

        Args:
        resource (str): The name of the resource.

        Returns:
        type[BaseMetricLoader]: The class of the metric loader corresponding to the resource.

        Raises:
        KeyError: If the specified resource is not registered.
        """

        try:
            return REGISTERED_METRICS[resource]
        except KeyError as e:
            raise KeyError(f"Resource {resource} was not registered by `@bind_metric(...)`") from e


Self = TypeVar("Self", bound=BaseMetricLoader)


def bind_metric(resource: str) -> Callable[[type[Self]], type[Self]]:
    """
    A decorator that binds a metric loader to a resource.

    Args:
    resource (str): The name of the resource.

    Returns:
    Callable[[type[Self]], type[Self]]: The decorator that does the binding.
    """

    def decorator(cls: type[Self]) -> type[Self]:
        REGISTERED_METRICS[resource] = cls
        return cls

    return decorator
