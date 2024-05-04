from robusta_krr.core.models.objects import K8sObjectData

from .base import PrometheusMetric, QueryType


class MemoryLoader(PrometheusMetric):
    """
    A metric loader for loading memory usage metrics.
    """

    query_type: QueryType = QueryType.QueryRange

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            max(
                container_memory_working_set_bytes{{
                    namespace="{object.namespace}",
                    pod=~"{pods_selector}",
                    container="{object.container}"
                    {cluster_label}
                }}
            ) by (container, pod, job)
        """


class MaxMemoryLoader(PrometheusMetric):
    """
    A metric loader for loading max memory usage metrics.
    """

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            max_over_time(
                max(
                    container_memory_working_set_bytes{{
                        namespace="{object.namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
                        {cluster_label}
                    }}
                ) by (container, pod, job)
                [{duration}:{step}]
            )
        """


class MemoryAmountLoader(PrometheusMetric):
    """
    A metric loader for loading memory points count.
    """

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            count_over_time(
                max(
                    container_memory_working_set_bytes{{
                        namespace="{object.namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
                        {cluster_label}
                    }}
                ) by (container, pod, job)
                [{duration}:{step}]
            )
        """

# TODO: Need to battle test if this one is correct.
class MaxOOMKilledMemoryLoader(PrometheusMetric):
    """
    A metric loader for loading the maximum memory limits that were surpassed by the OOMKilled event.
    """

    warning_on_no_data = False

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            max_over_time(
                max(
                    max(
                        kube_pod_container_resource_limits{{
                            resource="memory",
                            namespace="{object.namespace}",
                            pod=~"{pods_selector}",
                            container="{object.container}"
                            {cluster_label}
                        }} 
                    ) by (pod, container, job)
                    * on(pod, container, job) group_left(reason)
                    max(
                        kube_pod_container_status_last_terminated_reason{{
                            reason="OOMKilled",
                            namespace="{object.namespace}",
                            pod=~"{pods_selector}",
                            container="{object.container}"
                            {cluster_label}
                        }}
                    ) by (pod, container, job, reason)
                ) by (container, pod, job)
                [{duration}:{step}]
            )
        """
