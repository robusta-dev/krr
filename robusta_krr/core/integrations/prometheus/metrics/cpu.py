from robusta_krr.core.models.objects import K8sObjectData

from .base import QueryMetric, QueryRangeMetric, FilterMetric


class CPULoader(QueryRangeMetric, FilterMetric):
    def get_query(self, object: K8sObjectData, resolution: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            sum(
                irate(
                    container_cpu_usage_seconds_total{{
                        namespace="{object.namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
                        {cluster_label}
                    }}[5m]
                )
            ) by (container, pod, job)
        """


class MaxCPULoader(QueryMetric, FilterMetric):
    def get_query(self, object: K8sObjectData, resolution: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            max_over_time(
                irate(
                    container_cpu_usage_seconds_total{{
                        namespace="{object.namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
                        {cluster_label}
                    }}[{resolution}]
                )
            ) by (container, pod, job)
        """


def PercentileCPULoader(percentile: float) -> type[QueryMetric]:
    class PercentileCPULoader(QueryMetric, FilterMetric):
        def get_query(self, object: K8sObjectData, resolution: str) -> str:
            pods_selector = "|".join(pod.name for pod in object.pods)
            cluster_label = self.get_prometheus_cluster_label()
            return f"""
                quantile_over_time(
                    {round(percentile / 100, 2)},
                    irate(
                        container_cpu_usage_seconds_total{{
                            namespace="{object.namespace}",
                            pod=~"{pods_selector}",
                            container="{object.container}"
                            {cluster_label}
                        }}[1m]
                    )[{resolution}]
                )
            """

    return PercentileCPULoader
