from robusta_krr.core.models.objects import K8sObjectData

from .base import PrometheusMetric, QueryType
import logging

logger = logging.getLogger("krr")

class MemoryLoader(PrometheusMetric):
    """
    A metric loader for loading memory usage metrics.
    """

    query_type: QueryType = QueryType.QueryRange

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(self.get_vcluster_pod_real_name(pod.name, object.namespace) for pod in object.pods)
        pods_namespace = self.get_pod_namespace(object.namespace)
        cluster_label = self.get_prometheus_cluster_label()
        prom_query = f"""
            max(
                container_memory_working_set_bytes{{
                    namespace="{pods_namespace}",
                    pod=~"{pods_selector}",
                    container="{object.container}"
                    {cluster_label}
                }}
            ) by (container, pod, job)
        """
        logger.debug(f"{prom_query}")
        return prom_query


class MaxMemoryLoader(PrometheusMetric):
    """
    A metric loader for loading max memory usage metrics.
    """

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(self.get_vcluster_pod_real_name(pod.name, object.namespace) for pod in object.pods)
        pods_namespace = self.get_pod_namespace(object.namespace)
        cluster_label = self.get_prometheus_cluster_label()
        prom_query = f"""
            max_over_time(
                max(
                    container_memory_working_set_bytes{{
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

class MemoryAmountLoader(PrometheusMetric):
    """
    A metric loader for loading memory points count.
    """

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(self.get_vcluster_pod_real_name(pod.name, object.namespace) for pod in object.pods)
        pods_namespace = self.get_pod_namespace(object.namespace)
        cluster_label = self.get_prometheus_cluster_label()
        prom_query = f"""
            count_over_time(
                max(
                    container_memory_working_set_bytes{{
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
    
# TODO: Need to battle test if this one is correct.
class MaxOOMKilledMemoryLoader(PrometheusMetric):
    """
    A metric loader for loading the maximum memory limits that were surpassed by the OOMKilled event.
    """

    warning_on_no_data = False

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(self.get_vcluster_pod_real_name(pod.name, object.namespace) for pod in object.pods)
        pods_namespace = self.get_pod_namespace(object.namespace)
        cluster_label = self.get_prometheus_cluster_label()
        prom_query = f"""
            max_over_time(
                max(
                    max(
                        kube_pod_container_resource_limits{{
                            resource="memory",
                            namespace="{pods_namespace}",
                            pod=~"{pods_selector}",
                            container="{object.container}"
                            {cluster_label}
                        }} 
                    ) by (pod, container, job)
                    * on(pod, container, job) group_left(reason)
                    max(
                        kube_pod_container_status_last_terminated_reason{{
                            reason="OOMKilled",
                            namespace="{pods_namespace}",
                            pod=~"{pods_selector}",
                            container="{object.container}"
                            {cluster_label}
                        }}
                    ) by (pod, container, job, reason)
                ) by (container, pod, job)
                [{duration}:{step}]
            )
        """
        logger.debug(f"{prom_query}")
        return prom_query