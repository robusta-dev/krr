from robusta_krr.core.models.objects import K8sWorkload

from .base import PrometheusMetric, QueryType


class CPULoader(PrometheusMetric):
    """
    A metric loader for loading CPU usage metrics.
    """

    query_type: QueryType = QueryType.QueryRange

    def get_query(self, object: K8sWorkload, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        return f"""
            max(
                rate(
                    container_cpu_usage_seconds_total{{
                        {object.cluster_selector}
                        namespace="{object.namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
                    }}[{step}]
                )
            ) by (container, pod, job)
        """


def PercentileCPULoader(percentile: float) -> type[PrometheusMetric]:
    """
    A factory for creating percentile CPU usage metric loaders.
    """

    if not 0 <= percentile <= 100:
        raise ValueError("percentile must be between 0 and 100")

    class PercentileCPULoader(PrometheusMetric):
        def get_query(self, object: K8sWorkload, duration: str, step: str) -> str:
            pods_selector = "|".join(pod.name for pod in object.pods)
            return f"""
                quantile_over_time(
                    {round(percentile / 100, 2)},
                    max(
                        rate(
                            container_cpu_usage_seconds_total{{
                                {object.cluster_selector}
                                namespace="{object.namespace}",
                                pod=~"{pods_selector}",
                                container="{object.container}"
                            }}[{step}]
                        )
                    ) by (container, pod, job)
                    [{duration}:{step}]
                )
            """

    return PercentileCPULoader


class CPUAmountLoader(PrometheusMetric):
    """
    A metric loader for loading CPU points count.
    """

    def get_query(self, object: K8sWorkload, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        return f"""
            count_over_time(
                max(
                    container_cpu_usage_seconds_total{{
                        {object.cluster_selector}
                        namespace="{object.namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
                    }}
                ) by (container, pod, job)
                [{duration}:{step}]
            )
        """
