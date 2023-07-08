from __future__ import annotations

import abc
import asyncio
from concurrent.futures import ThreadPoolExecutor
import datetime
from typing import TYPE_CHECKING, Callable, Optional, TypeVar
import enum
import numpy as np
from robusta_krr.core.abstract.strategies import Metric, ResourceHistoryData
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.utils.configurable import Configurable

if TYPE_CHECKING:
    from .. import CustomPrometheusConnect

    MetricsDictionary = dict[str, type[BaseMetricLoader]]


class QueryType(str, enum.Enum):
    Query = "query"
    QueryRange = "query_range"


# A registry of metrics that can be used to fetch a corresponding metric loader.
REGISTERED_METRICS: MetricsDictionary = {}
STRATEGY_METRICS_OVERRIDES: dict[str, MetricsDictionary] = {}


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
    def get_query(self, object: K8sObjectData, resolution: Optional[str]) -> str:
        """
        This method should be implemented by all subclasses to provide a query string to fetch metrics.

        Args:
        object (K8sObjectData): The object for which metrics need to be fetched.
        resolution (Optional[str]): a string for configurable resolution to the query.

        Returns:
        str: The query string.
        """

        pass

    def get_graph_query(self, object: K8sObjectData, resolution: Optional[str]) -> str:
        """
        This method should be implemented by all subclasses to provide a query string in the metadata to produce relevant graphs.

        Args:
        object (K8sObjectData): The object for which metrics need to be fetched.
        resolution (Optional[str]): a string for configurable resolution to the query.

        Returns:
        str: The query string.
        """
        return self.get_query(object, resolution)

    def _step_to_string(self, step: datetime.timedelta) -> str:
        """
        Converts step in datetime.timedelta format to a string format used by Prometheus.

        Args:
        step (datetime.timedelta): Step size in datetime.timedelta format.

        Returns:
        str: Step size in string format used by Prometheus.
        """
        if step.total_seconds() > 60 * 60 * 24:
            return f"{int(step.total_seconds()) // (60 * 60 * 24)}d"
        return f"{int(step.total_seconds()) // 60}m"

    def query_prometheus_thread(self, metric: Metric, query_type: QueryType) -> list[dict]:
        if query_type == QueryType.QueryRange:
            value = self.prometheus.custom_query_range(
                query=metric.query,
                start_time=metric.start_time,
                end_time=metric.end_time,
                step=metric.step,
            )
            return value

        # regular query, lighter on preformance
        results = self.prometheus.custom_query(query=metric.query)
        # format the results to return the same format as custom_query_range
        for result in results:
            result["values"] = [result.pop("value")]
        return results

    async def query_prometheus(self, metric: Metric, query_type: QueryType) -> list[dict]:
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
            lambda: self.query_prometheus_thread(metric=metric, query_type=query_type),
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
        resolution = f"{self._step_to_string(period)}:{self._step_to_string(step)}"
        query = self.get_query(object, resolution)
        query_type = self.get_query_type()
        end_time = datetime.datetime.now().astimezone()
        metric = Metric(
            query=query,
            start_time=end_time - period,
            end_time=end_time,
            step=self._step_to_string(step),
        )
        result = await self.query_prometheus(metric=metric, query_type=query_type)
        # adding the query in the results for a graph 
        metric.query = self.get_graph_query(object, resolution)

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
    def get_by_resource(resource: str, strategy: Optional[str]) -> type[BaseMetricLoader]:
        """
        Fetches the metric loader corresponding to the specified resource.

        Args:
        resource (str): The name of the resource.
        resource (str): The name of the strategy.

        Returns:
        type[BaseMetricLoader]: The class of the metric loader corresponding to the resource.

        Raises:
        KeyError: If the specified resource is not registered.
        """

        try:
            lower_strategy = strategy.lower()
            if (
                lower_strategy
                and lower_strategy in STRATEGY_METRICS_OVERRIDES
                and resource in STRATEGY_METRICS_OVERRIDES[lower_strategy]
            ):
                return STRATEGY_METRICS_OVERRIDES[lower_strategy][resource]
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


# This is a temporary solutions, metric loaders will be moved to strategy in the future
def override_metric(strategy: str, resource: str) -> Callable[[type[Self]], type[Self]]:
    """
    A decorator that overrides the bound metric on a specific strategy.

    Args:
    strategy (str): The name of the strategy for this metric.
    resource (str): The name of the resource.

    Returns:
    Callable[[type[Self]], type[Self]]: The decorator that does the binding.
    """

    def decorator(cls: type[Self]) -> type[Self]:
        lower_strategy = strategy.lower()
        if lower_strategy not in STRATEGY_METRICS_OVERRIDES:
            STRATEGY_METRICS_OVERRIDES[lower_strategy] = {}
        STRATEGY_METRICS_OVERRIDES[lower_strategy][resource] = cls
        return cls

    return decorator
