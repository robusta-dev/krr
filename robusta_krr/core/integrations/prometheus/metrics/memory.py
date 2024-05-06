from robusta_krr.core.models.objects import K8sWorkload

from .base import PrometheusMetric, QueryType


class MemoryLoader(PrometheusMetric):
    """
    A metric loader for loading memory usage metrics.
    """

    query_type: QueryType = QueryType.QueryRange

    def get_query(self, object: K8sWorkload, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        return f"""
            max(
                container_memory_working_set_bytes{{
                    {object.cluster_selector}
                    namespace="{object.namespace}",
                    pod=~"{pods_selector}",
                    container="{object.container}"
                }}
            ) by (container, pod, job)
        """


class MaxMemoryLoader(PrometheusMetric):
    """
    A metric loader for loading max memory usage metrics.
    """

    def get_query(self, object: K8sWorkload, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        return f"""
            max_over_time(
                max(
                    container_memory_working_set_bytes{{
                        {object.cluster_selector}
                        namespace="{object.namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
                    }}
                ) by (container, pod, job)
                [{duration}:{step}]
            )
        """


class MemoryAmountLoader(PrometheusMetric):
    """
    A metric loader for loading memory points count.
    """

    def get_query(self, object: K8sWorkload, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        return f"""
            count_over_time(
                max(
                    container_memory_working_set_bytes{{
                        {object.cluster_selector}
                        namespace="{object.namespace}",
                        pod=~"{pods_selector}",
                        container="{object.container}"
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

    def get_query(self, object: K8sWorkload, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        return f"""
            max_over_time(
                max(
                    max(
                        kube_pod_container_resource_limits{{
                            {object.cluster_selector}
                            resource="memory",
                            namespace="{object.namespace}",
                            pod=~"{pods_selector}",
                            container="{object.container}"
                        }}
                    ) by (pod, container, job)
                    * on(pod, container, job) group_left(reason)
                    max(
                        kube_pod_container_status_last_terminated_reason{{
                            {object.cluster_selector}
                            reason="OOMKilled",
                            namespace="{object.namespace}",
                            pod=~"{pods_selector}",
                            container="{object.container}"
                        }}
                    ) by (pod, container, job, reason)
                ) by (container, pod, job)
                [{duration}:{step}]
            )
        """
