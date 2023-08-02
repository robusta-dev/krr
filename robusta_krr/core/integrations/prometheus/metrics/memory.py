from robusta_krr.core.abstract.strategies import PodsTimeData

from robusta_krr.core.models.objects import K8sObjectData

from .base import QueryMetric, QueryRangeMetric, FilterJobsMixin, BatchedRequestMixin


class MemoryLoader(QueryRangeMetric, FilterJobsMixin, BatchedRequestMixin):
    def get_query(self, object: K8sObjectData, resolution: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            sum(
                container_memory_working_set_bytes{{
                    namespace="{object.namespace}",
                    pod=~"{pods_selector}",
                    container="{object.container}"
                    {cluster_label}
                }}
            ) by (container, pod, job, id)
        """


class MaxMemoryLoader(QueryMetric, FilterJobsMixin, BatchedRequestMixin):
    def get_query(self, object: K8sObjectData, resolution: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            max_over_time(
                container_memory_working_set_bytes{{
                    namespace="{object.namespace}",
                    pod=~"{pods_selector}",
                    container="{object.container}"
                    {cluster_label}
                }}[{resolution}]
            )
        """


def PercentileMemoryLoader(percentile: float) -> type[QueryMetric]:
    class PercentileMemoryLoader(QueryMetric, FilterJobsMixin, BatchedRequestMixin):
        def get_query(self, object: K8sObjectData, resolution: str) -> str:
            pods_selector = "|".join(pod.name for pod in object.pods)
            cluster_label = self.get_prometheus_cluster_label()
            return f"""
                quantile_over_time(
                    {round(percentile / 100, 2)},
                    container_memory_working_set_bytes{{
                        namespace="{object.namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
                        {cluster_label}
                    }}[{resolution}]
                )
            """

    return PercentileMemoryLoader
