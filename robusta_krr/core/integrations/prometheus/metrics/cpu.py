from robusta_krr.core.models.objects import K8sObjectData

from .base import BatchedRequestMixin, FilterJobsMixin, QueryMetric, QueryRangeMetric


class CPULoader(QueryRangeMetric, FilterJobsMixin, BatchedRequestMixin):
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
                    }}[{resolution}]
                )
            ) by (container, pod, job)
        """


class MaxCPULoader(QueryMetric, FilterJobsMixin, BatchedRequestMixin):
    def get_query(self, object: K8sObjectData, resolution: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            max(sum(
                irate(
                    container_cpu_usage_seconds_total{{
                        namespace="{object.namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
                        {cluster_label}
                    }}[{resolution}]
                )
            ) by (container, pod, job) ) by (container, pod, job)
        """


def PercentileCPULoader(percentile: float) -> type[QueryMetric]:
    class PercentileCPULoader(QueryMetric, FilterJobsMixin, BatchedRequestMixin):
        def get_query(self, object: K8sObjectData, resolution: str) -> str:
            pods_selector = "|".join(pod.name for pod in object.pods)
            cluster_label = self.get_prometheus_cluster_label()
            return f"""
                quantile(
                    {round(percentile / 100, 2)},
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

    return PercentileCPULoader
