from robusta_krr.core.models.objects import K8sObjectData

from .base import BatchedRequestMixin, FilterJobsMixin, QueryMetric, QueryRangeMetric


class CPULoader(QueryRangeMetric, FilterJobsMixin, BatchedRequestMixin):
    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            rate(
                container_cpu_usage_seconds_total{{
                    namespace="{object.namespace}",
                    pod=~"{pods_selector}",
                    container="{object.container}"
                    {cluster_label}
                }}[{step}]
            )
        """


def PercentileCPULoader(percentile: float) -> type[QueryMetric]:
    class PercentileCPULoader(QueryMetric, FilterJobsMixin, BatchedRequestMixin):
        def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
            pods_selector = "|".join(pod.name for pod in object.pods)
            cluster_label = self.get_prometheus_cluster_label()
            return f"""
                quantile_over_time(
                    {round(percentile / 100, 2)},
                    rate(
                        container_cpu_usage_seconds_total{{
                            namespace="{object.namespace}",
                            pod=~"{pods_selector}",
                            container="{object.container}"
                            {cluster_label}
                        }}[{step}]
                    )[{duration}:{step}]
                )
            """

    return PercentileCPULoader


class CPUAmountLoader(QueryMetric, FilterJobsMixin, BatchedRequestMixin):
    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            count_over_time(
                container_cpu_usage_seconds_total{{
                    namespace="{object.namespace}",
                    pod=~"{pods_selector}",
                    container="{object.container}"
                    {cluster_label}
                }}[{duration}]
            )
        """
