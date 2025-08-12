from robusta_krr.core.models.objects import K8sObjectData

from .base import PrometheusMetric, QueryType
import logging

logger = logging.getLogger("krr")
    
class CPULoader(PrometheusMetric):
    """
    A metric loader for loading CPU usage metrics.
    """

    query_type: QueryType = QueryType.QueryRange

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(self.get_vcluster_pod_real_name(pod.name, object.namespace) for pod in object.pods)
        pods_namespace = self.get_pod_namespace(object.namespace)
        cluster_label = self.get_prometheus_cluster_label()
        prom_query = f"""
            max(
                    rate(
                        container_cpu_usage_seconds_total{{
                            namespace="{pods_namespace}",
                            pod=~"{pods_selector}",
                            container="{object.container}"
                            {cluster_label}
                        }}[{step}]
                    )
                ) by (container, pod, job)
            """
        logger.debug(f"{prom_query}")

        return prom_query


def PercentileCPULoader(percentile: float) -> type[PrometheusMetric]:
    """
    A factory for creating percentile CPU usage metric loaders.
    """

    if not 0 <= percentile <= 100:
        raise ValueError("percentile must be between 0 and 100")

    class PercentileCPULoader(PrometheusMetric):
        def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
            pods_selector = "|".join(self.get_vcluster_pod_real_name(pod.name, object.namespace) for pod in object.pods)
            pods_namespace = self.get_pod_namespace(object.namespace)
            cluster_label = self.get_prometheus_cluster_label()
            prom_query = f"""
                quantile_over_time(
                    {round(percentile / 100, 2)},
                    max(
                        rate(
                            container_cpu_usage_seconds_total{{
                                namespace="{pods_namespace}",
                                pod=~"{pods_selector}",
                                container="{object.container}"
                                {cluster_label}
                            }}[{step}]
                        )
                    ) by (container, pod, job)
                    [{duration}:{step}]
                )
            """
            logger.debug(f"{prom_query}")
            return prom_query

    return PercentileCPULoader


class CPUAmountLoader(PrometheusMetric):
    """
    A metric loader for loading CPU points count.
    """

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(self.get_vcluster_pod_real_name(pod.name, object.namespace) for pod in object.pods)
        pods_namespace = self.get_pod_namespace(object.namespace)
        cluster_label = self.get_prometheus_cluster_label()
        prom_query = f"""
            count_over_time(
                max(
                    container_cpu_usage_seconds_total{{
                        namespace="{pods_namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
                        {cluster_label}
                    }}
                ) by (container, pod, job)
                [{duration}:{step}]
            )
        """
        logger.debug(f"{prom_query}")
        return prom_query
