from typing import Any, Optional
from robusta_krr.core.abstract.strategies import Metric

from .base_metric import BaseMetricLoader, QueryType

PrometheusSeries = Any


class BaseFilteredMetricLoader(BaseMetricLoader):
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
            BaseFilteredMetricLoader.get_target_name(series)
            for series in series_list_result
            if BaseFilteredMetricLoader.get_target_name(series)
        }
        return_list: list[PrometheusSeries] = []

        # takes kubelet job if exists, return first job alphabetically if it doesn't
        for target_name in target_names:
            relevant_series = [
                series
                for series in series_list_result
                if BaseFilteredMetricLoader.get_target_name(series) == target_name
            ]
            relevant_kubelet_metric = [series for series in relevant_series if series["metric"].get("job") == "kubelet"]
            if len(relevant_kubelet_metric) == 1:
                return_list.append(relevant_kubelet_metric[0])
                continue
            sorted_relevant_series = sorted(relevant_series, key=lambda s: s["metric"].get("job"), reverse=False)
            return_list.append(sorted_relevant_series[0])
        return return_list

    async def query_prometheus(self, metric: Metric, query_type: QueryType) -> list[PrometheusSeries]:
        result = await super().query_prometheus(metric, query_type)
        return self.filter_prom_jobs_results(result)
