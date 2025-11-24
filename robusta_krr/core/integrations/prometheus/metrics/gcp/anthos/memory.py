"""
Memory metric loaders for GCP Anthos (on-prem Kubernetes managed by Google).

Anthos uses kubernetes.io/anthos/container/* metrics with max_over_time
aggregation for memory (different from GKE's max_over_time).
"""

from robusta_krr.core.models.objects import K8sObjectData
from ...base import PrometheusMetric


class AnthosMemoryLoader(PrometheusMetric):
    """
    Loads memory usage metrics from GCP Anthos Managed Prometheus.
    
    Uses max_over_time aggregation as per Anthos convention.
    """
    
    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            label_replace(
                label_replace(
                    max(
                        {{"__name__"="kubernetes.io/anthos/container/memory/used_bytes",
                            "monitored_resource"="k8s_container",
                            "namespace_name"="{object.namespace}",
                            "pod_name"=~"{pods_selector}",
                            "container_name"="{object.container}"{cluster_label}
                        }}
                    ) by (container_name, pod_name, job),
                    "pod", "$1", "pod_name", "(.+)"
                ),
                "container", "$1", "container_name", "(.+)"
            )
        """


class AnthosMaxMemoryLoader(PrometheusMetric):
    """
    Loads maximum memory usage from GCP Anthos Managed Prometheus.
    
    Uses max_over_time for aggregation (Anthos convention).
    """
    
    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            label_replace(
                label_replace(
                    max_over_time(
                        max(
                            {{"__name__"="kubernetes.io/anthos/container/memory/used_bytes",
                                "monitored_resource"="k8s_container",
                                "namespace_name"="{object.namespace}",
                                "pod_name"=~"{pods_selector}",
                                "container_name"="{object.container}"{cluster_label}
                            }}
                        ) by (container_name, pod_name, job)
                        [{duration}:{step}]
                    ),
                    "pod", "$1", "pod_name", "(.+)"
                ),
                "container", "$1", "container_name", "(.+)"
            )
        """


class AnthosMemoryAmountLoader(PrometheusMetric):
    """
    Loads memory amount (count of containers) for Anthos.
    """
    
    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        return f"""
            label_replace(
                label_replace(
                    count_over_time(
                        max(
                            {{"__name__"="kubernetes.io/anthos/container/memory/used_bytes",
                                "monitored_resource"="k8s_container",
                                "namespace_name"="{object.namespace}",
                                "pod_name"=~"{pods_selector}",
                                "container_name"="{object.container}"{cluster_label}
                            }}
                        ) by (container_name, pod_name, job)
                        [{duration}:{step}]
                    ),
                    "pod", "$1", "pod_name", "(.+)"
                ),
                "container", "$1", "container_name", "(.+)"
            )
        """
