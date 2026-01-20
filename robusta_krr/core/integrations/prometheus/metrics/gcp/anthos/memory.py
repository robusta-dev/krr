"""
Memory metric loaders for GCP Anthos (on-prem Kubernetes managed by Google).

Anthos uses kubernetes.io/anthos/container/* metrics for memory, matching
the GKE aggregation patterns but with a different metric namespace.
"""

import logging

from robusta_krr.core.models.objects import K8sObjectData
from ...base import PrometheusMetric


logger = logging.getLogger("krr")


class AnthosMemoryLoader(PrometheusMetric):
    """Loads memory usage metrics from Anthos' kubernetes.io/anthos namespace."""
    
    def get_query(self, object: K8sObjectData, _duration: str, _step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        query = f"""
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
        logger.debug(
            "Anthos memory usage query for %s/%s/%s:\n%s",
            object.namespace,
            object.name,
            object.container,
            query.strip(),
        )
        return query


class AnthosMaxMemoryLoader(PrometheusMetric):
    """Loads max memory usage using Anthos' kubernetes.io/anthos metrics."""
    
    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        query = f"""
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
        logger.debug(
            "Anthos max memory query for %s/%s/%s:\n%s",
            object.namespace,
            object.name,
            object.container,
            query.strip(),
        )
        return query


class AnthosMemoryAmountLoader(PrometheusMetric):
    """
    Loads memory amount (count of containers) for Anthos.
    """
    
    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        query = f"""
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
        logger.debug(
            "Anthos memory amount query for %s/%s/%s:\n%s",
            object.namespace,
            object.name,
            object.container,
            query.strip(),
        )
        return query


class AnthosMaxOOMKilledMemoryLoader(PrometheusMetric):
    """
    A metric loader for loading the maximum memory limits that were surpassed by OOMKilled events.
    
    Anthos Managed Prometheus does not provide kube_pod_container_status_last_terminated_reason,
    so this implementation uses an inference-based approach by combining:
    - kubernetes.io/anthos/container/memory/limit_bytes (memory limit)
    - kubernetes.io/anthos/container/restart_count (container restarts)
    
    This approach may produce false positives if containers restart for reasons other than OOM
    while memory usage is high.
    """

    warning_on_no_data = False

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        
        # Anthos OOM detection uses inference: restart_count * memory_limit
        # This assumes that restarts near memory limit indicate OOM events
        query = f"""
            label_replace(
                label_replace(
                    max_over_time(
                        max(
                            max(
                                {{"__name__"="kubernetes.io/anthos/container/memory/limit_bytes",
                                    "monitored_resource"="k8s_container",
                                    "namespace_name"="{object.namespace}",
                                    "pod_name"=~"{pods_selector}",
                                    "container_name"="{object.container}"{cluster_label}
                                }}
                            ) by (pod_name, container_name, job)
                            
                            * on(pod_name, container_name, job) group_left()
                            
                            max(
                                {{"__name__"="kubernetes.io/anthos/container/restart_count",
                                    "monitored_resource"="k8s_container",
                                    "namespace_name"="{object.namespace}",
                                    "pod_name"=~"{pods_selector}",
                                    "container_name"="{object.container}"{cluster_label}
                                }}
                            ) by (pod_name, container_name, job)
                        ) by (container_name, pod_name, job)
                        [{duration}:{step}]
                    ),
                    "pod", "$1", "pod_name", "(.+)"
                ),
                "container", "$1", "container_name", "(.+)"
            )
        """
        logger.info(
            "Anthos OOM detection query (inference-based using restart_count + memory limit) for %s/%s/%s:",
            object.namespace,
            object.name,
            object.container,
        )
        logger.debug("Query:\n%s", query.strip())
        return query
