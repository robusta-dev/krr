from robusta_krr.core.models.objects import K8sObjectData

from .base import PrometheusMetric, QueryType


class CPULoader(PrometheusMetric):
    """
    A metric loader for loading CPU usage metrics.
    """

    query_type: QueryType = QueryType.QueryRange

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


def PercentileCPULoader(percentile: float) -> type[PrometheusMetric]:
    """
    A factory for creating percentile CPU usage metric loaders.
    """

    if not 0 <= percentile <= 100:
        raise ValueError("percentile must be between 0 and 100")

    class PercentileCPULoader(PrometheusMetric):
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


class CPUAmountLoader(PrometheusMetric):
    """
    A metric loader for loading CPU points count.
    """

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
