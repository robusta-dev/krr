from __future__ import annotations

import abc
import asyncio
import datetime
import enum
from concurrent.futures import ThreadPoolExecutor
from functools import reduce
from typing import Any, Optional, TypedDict

import numpy as np
import pydantic as pd
from prometrix import CustomPrometheusConnect
from tenacity import retry, stop_after_attempt, wait_random

from robusta_krr.core.abstract.metrics import BaseMetric
from robusta_krr.core.abstract.strategies import PodsTimeData
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import K8sObjectData


class PrometheusSeries(TypedDict):
    metric: dict[str, Any]
    values: list[list[float]]


class QueryType(str, enum.Enum):
    Query = "query"
    QueryRange = "query_range"


class PrometheusMetricData(pd.BaseModel):
    query: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    step: str
    type: QueryType


class PrometheusMetric(BaseMetric):
    """
    Base class for all metric loaders.

    Metric loaders are used to load metrics from a specified source (like Prometheus in this case).

    `query_type`: the type of query to use when querying Prometheus.
    Can be either `QueryType.Query` or `QueryType.QueryRange`.
    By default, `QueryType.Query` is used.

    `filtering`: if multiple metrics with the same name were found, searches for the kubelet metric.
    If not found - returns first one in alphabetical order. Set to False if you want to disable this behavior.

    `pods_batch_size`: if the number of pods is too large for a single query, the query is split into multiple sub-queries.
    Each sub-query result is then combined into a single result using the `combine_batches` method.
    You can override this method to change the way the results are combined.
    This parameter specifies the maximum number of pods per query.
    Set to None to disable batching
    """

    query_type: QueryType = QueryType.Query
    filtering: bool = True
    pods_batch_size: Optional[int] = 50
    warning_on_no_data: bool = True

    def __init__(
        self,
        prometheus: CustomPrometheusConnect,
        service_name: str,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        self.prometheus = prometheus
        self.service_name = service_name

        self.executor = executor

        if self.pods_batch_size is not None and self.pods_batch_size <= 0:
            raise ValueError("pods_batch_size must be positive")

    def get_prometheus_cluster_label(self) -> str:
        """
        Generates the cluster label for querying a centralized Prometheus

        Returns:
        str: a promql safe label string for querying the cluster.
        """
        if settings.prometheus_cluster_label is None:
            return ""
        return f', {settings.prometheus_label}="{settings.prometheus_cluster_label}"'

    @abc.abstractmethod
    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        """
        This method should be implemented by all subclasses to provide a query string to fetch metrics.

        Args:
        object (K8sObjectData): The object for which metrics need to be fetched.
        duration (str): a string for duration of the query.
        step (str): a string for the step size of the query.

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

    @retry(wait=wait_random(min=2, max=10), stop=stop_after_attempt(5))
    def _query_prometheus_sync(self, data: PrometheusMetricData) -> list[PrometheusSeries]:
        if data.type == QueryType.QueryRange:
            response = self.prometheus.safe_custom_query_range(
                query=data.query,
                start_time=data.start_time,
                end_time=data.end_time,
                step=data.step,
            )
            return response["result"]
        else:
            # regular query, lighter on preformance
            try:
                response = self.prometheus.safe_custom_query(query=data.query)
            except Exception as e:
                raise ValueError(f"Failed to run query: {data.query}") from e
            results = response["result"]
            # format the results to return the same format as custom_query_range
            for result in results:
                result["values"] = [result.pop("value")]
            return results

    async def query_prometheus(self, data: PrometheusMetricData) -> list[PrometheusSeries]:
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

        step_str = f"{round(step.total_seconds())}s"
        duration_str = self._step_to_string(period)

        query = self.get_query(object, duration_str, step_str)
        end_time = datetime.datetime.utcnow().replace(second=0, microsecond=0)
        start_time = end_time - period

        # Here if we split the object into multiple sub-objects, we query each sub-object recursively.
        if self.pods_batch_size is not None and object.pods_count > self.pods_batch_size:
            results = await asyncio.gather(
                *[
                    self.load_data(splitted_object, period, step)
                    for splitted_object in object.split_into_batches(self.pods_batch_size)
                ]
            )
            return self.combine_batches(results)

        result = await self.query_prometheus(
            PrometheusMetricData(
                query=query,
                start_time=start_time,
                end_time=end_time,
                step=step_str,
                type=self.query_type,
            )
        )

        if result == []:
            return {}

        if self.filtering:
            result = self.filter_prom_jobs_results(result)

        return {pod_result["metric"]["pod"]: np.array(pod_result["values"], dtype=np.float64) for pod_result in result}

    # --------------------- Filtering Jobs --------------------- #

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
            PrometheusMetric.get_target_name(series)
            for series in series_list_result
            if PrometheusMetric.get_target_name(series)
        }
        return_list: list[PrometheusSeries] = []

        # takes kubelet job if exists, return first job alphabetically if it doesn't
        for target_name in target_names:
            relevant_series = [
                series for series in series_list_result if PrometheusMetric.get_target_name(series) == target_name
            ]
            relevant_kubelet_metric = [series for series in relevant_series if series["metric"].get("job") == "kubelet"]
            if len(relevant_kubelet_metric) == 1:
                return_list.append(relevant_kubelet_metric[0])
                continue
            sorted_relevant_series = sorted(relevant_series, key=lambda s: s["metric"].get("job", ""), reverse=False)
            return_list.append(sorted_relevant_series[0])
        return return_list

    # --------------------- Batching Queries --------------------- #

    def combine_batches(self, results: list[PodsTimeData]) -> PodsTimeData:
        """
        Combines the results of multiple queries into a single result.

        Args:
        results (list[MetricPodData]): A list of query results.

        Returns:
        MetricPodData: A combined result.
        """

        return reduce(lambda x, y: x | y, results, {})
