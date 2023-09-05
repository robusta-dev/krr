from robusta_krr.core.models.objects import K8sObjectData

from .base import BatchedRequestMixin, FilterJobsMixin, QueryMetric, QueryRangeMetric


class CPULoader(QueryRangeMetric, FilterJobsMixin, BatchedRequestMixin):
    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            max(
                rate(
                    container_cpu_usage_seconds_total{{
                        namespace="{object.namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
                        {cluster_label}
                    }}[{step}]
                )
            ) by (container, pod, job)
        """


def PercentileCPULoader(percentile: float) -> type[QueryMetric]:
    class PercentileCPULoader(QueryMetric, FilterJobsMixin, BatchedRequestMixin):
        def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
            pods_selector = "|".join(pod.name for pod in object.pods)
            cluster_label = self.get_prometheus_cluster_label()
            return f"""
                quantile_over_time(
                    {round(percentile / 100, 2)},
                    max(
                        rate(
                            container_cpu_usage_seconds_total{{
                                namespace="{object.namespace}",
                                pod=~"{pods_selector}",
                                container="{object.container}"
                                {cluster_label}
                            }}[{step}]
                        )
                    ) by (container, pod, job)
                    [{duration}:{step}]
                )
            """

    return PercentileCPULoader


class CPUAmountLoader(QueryMetric, FilterJobsMixin, BatchedRequestMixin):
    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            count_over_time(
                max(
                    container_cpu_usage_seconds_total{{
                        namespace="{object.namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
                        {cluster_label}
                    }}
                ) by (container, pod, job)
                [{duration}:{step}]
            )
        """
