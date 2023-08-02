from __future__ import annotations

import abc
import asyncio
import datetime
import enum
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TYPE_CHECKING, Optional

import numpy as np
import pydantic as pd

from robusta_krr.core.abstract.metrics import BaseMetric
from robusta_krr.core.abstract.strategies import PodsTimeData
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.utils.configurable import Configurable

if TYPE_CHECKING:
    from .. import CustomPrometheusConnect


class QueryType(str, enum.Enum):
    Query = "query"
    QueryRange = "query_range"


class PrometheusMetricData(pd.BaseModel):
    query: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    step: str
    type: QueryType


class PrometheusMetric(BaseMetric, Configurable):
    """
    Base class for all metric loaders.

    Metric loaders are used to load metrics from a specified source (like Prometheus in this case).
    """

    query_type: QueryType = QueryType.QueryRange

    def __init__(
        self,
        config: Config,
        prometheus: CustomPrometheusConnect,
        service_name: str,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        super().__init__(config)
        self.prometheus = prometheus
        self.service_name = service_name

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
    def get_query(self, object: K8sObjectData, resolution: str) -> str:
        """
        This method should be implemented by all subclasses to provide a query string to fetch metrics.

        Args:
        object (K8sObjectData): The object for which metrics need to be fetched.
        resolution (Optional[str]): a string for configurable resolution to the query.

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
        if step.total_seconds() > 60 * 60 * 24:
            return f"{int(step.total_seconds()) // (60 * 60 * 24)}d"
        return f"{int(step.total_seconds()) // 60}m"

    def _query_prometheus_sync(self, data: PrometheusMetricData) -> list[dict]:
        if data.type == QueryType.QueryRange:
            value = self.prometheus.custom_query_range(
                query=data.query,
                start_time=data.start_time,
                end_time=data.end_time,
                step=data.step,
            )
            return value
        else:
            # regular query, lighter on preformance
            results = self.prometheus.custom_query(query=data.query)
            # format the results to return the same format as custom_query_range
            for result in results:
                result["values"] = [result.pop("value")]
            return results

    async def query_prometheus(self, data: PrometheusMetricData) -> list[dict]:
        """
        Asynchronous method that queries Prometheus to fetch metrics.

        Args:
        metric (Metric): An instance of the Metric class specifying what metrics to fetch.

        Returns:
        list[dict]: A list of dictionary where each dictionary represents metrics for a pod.
        """

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, lambda: self._query_prometheus_sync(data))

    async def load_data(
        self, object: K8sObjectData, period: datetime.timedelta, step: datetime.timedelta
    ) -> PodsTimeData:
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
        end_time = datetime.datetime.now().astimezone()
        start_time = end_time - period

        result = await self.query_prometheus(
            PrometheusMetricData(
                query=query,
                start_time=start_time,
                end_time=end_time,
                step=self._step_to_string(step),
                type=self.query_type,
            )
        )

        if result == []:
            self.warning(f"{self.service_name} returned no {self.__class__.__name__} metrics for {object}")
            return {}

        return {pod_result["metric"]["pod"]: np.array(pod_result["values"], dtype=np.float64) for pod_result in result}


class QueryRangeMetric(PrometheusMetric):
    """This type of PrometheusMetric is used to query metrics for a specific time range."""

    query_type = QueryType.QueryRange


class QueryMetric(PrometheusMetric):
    """This type of PrometheusMetric is used to query metrics for a specific time."""

    query_type = QueryType.Query


PrometheusSeries = Any


class FilterMetric(PrometheusMetric):
    """
    This is the version of the BasicMetricLoader, that filters out data,
    if multiple metrics with the same name were found.

    Searches for the kubelet metric. If not found - returns first one in alphabetical order.
    """

    @staticmethod
    def get_target_name(series: PrometheusSeries) -> Optional[str]:
        for label in ["pod", "container", "node"]:
            if label in series["metric"]:
                return series["metric"][label]
        return None

    @staticmethod
    def filter_prom_jobs_results(
        series_list_result: list[PrometheusSeries],
    ) -> list[PrometheusSeries]:
        """
        Because there might be multiple metrics with the same name, we need to filter them out.

        :param series_list_result: list of PrometheusSeries
        """

        if len(series_list_result) == 1:
            return series_list_result

        target_names = {
            FilterMetric.get_target_name(series)
            for series in series_list_result
            if FilterMetric.get_target_name(series)
        }
        return_list: list[PrometheusSeries] = []

        # takes kubelet job if exists, return first job alphabetically if it doesn't
        for target_name in target_names:
            relevant_series = [
                series for series in series_list_result if FilterMetric.get_target_name(series) == target_name
            ]
            relevant_kubelet_metric = [series for series in relevant_series if series["metric"].get("job") == "kubelet"]
            if len(relevant_kubelet_metric) == 1:
                return_list.append(relevant_kubelet_metric[0])
                continue
            sorted_relevant_series = sorted(relevant_series, key=lambda s: s["metric"].get("job"), reverse=False)
            return_list.append(sorted_relevant_series[0])
        return return_list

    async def query_prometheus(self, data: PrometheusMetricData) -> list[PrometheusSeries]:
        result = await super().query_prometheus(data)
        return self.filter_prom_jobs_results(result)
