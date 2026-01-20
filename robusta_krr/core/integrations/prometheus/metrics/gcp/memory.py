"""
GCP Managed Prometheus Memory metric loaders.

These loaders use GCP's kubernetes.io/container/memory/used_bytes metric
with UTF-8 PromQL syntax required by GCP Managed Prometheus.

Note: MaxOOMKilledMemoryLoader is not implemented as it relies on kube-state-metrics
which may not be available in GCP Managed Prometheus.
"""

import logging

from robusta_krr.core.models.objects import K8sObjectData

from ..base import PrometheusMetric, QueryType


logger = logging.getLogger("krr")


class GcpMemoryLoader(PrometheusMetric):
    """
    A metric loader for loading memory usage metrics from GCP Managed Prometheus.
    Uses kubernetes.io/container/memory/used_bytes instead of container_memory_working_set_bytes.
    """

    query_type: QueryType = QueryType.QueryRange

    def get_query(self, object: K8sObjectData, _duration: str, _step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        
        # GCP requires UTF-8 syntax with quoted metric names and labels
        # We also rename GCP labels for compatibility with existing code
        query = f"""
            label_replace(
                label_replace(
                    max(
                        {{"__name__"="kubernetes.io/container/memory/used_bytes",
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
            "GCP memory usage query for %s/%s/%s:\n%s",
            object.namespace,
            object.name,
            object.container,
            query.strip(),
        )
        return query


class GcpMaxMemoryLoader(PrometheusMetric):
    """
    A metric loader for loading max memory usage metrics from GCP Managed Prometheus.
    """

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        query = f"""
            label_replace(
                label_replace(
                    max_over_time(
                        max(
                            {{"__name__"="kubernetes.io/container/memory/used_bytes",
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
            "GCP max memory query for %s/%s/%s:\n%s",
            object.namespace,
            object.name,
            object.container,
            query.strip(),
        )
        return query


class GcpMemoryAmountLoader(PrometheusMetric):
    """
    A metric loader for loading memory data points count from GCP Managed Prometheus.
    """

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        query = f"""
            label_replace(
                label_replace(
                    count_over_time(
                        max(
                            {{"__name__"="kubernetes.io/container/memory/used_bytes",
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
            "GCP memory amount query for %s/%s/%s:\n%s",
            object.namespace,
            object.name,
            object.container,
            query.strip(),
        )
        return query


class GcpMaxOOMKilledMemoryLoader(PrometheusMetric):
    """
    A metric loader for loading the maximum memory limits that were surpassed by OOMKilled events.
    
    GCP Managed Prometheus does not provide kube_pod_container_status_last_terminated_reason,
    so this implementation uses an inference-based approach by combining:
    - kubernetes.io/container/memory/limit_bytes (memory limit)
    - kubernetes.io/container/restart_count (container restarts)
    
    This approach may produce false positives if containers restart for reasons other than OOM
    while memory usage is high.
    """

    warning_on_no_data = False

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        
        # GCP OOM detection uses inference: restart_count * memory_limit
        # This assumes that restarts near memory limit indicate OOM events
        query = f"""
            label_replace(
                label_replace(
                    max_over_time(
                        max(
                            max(
                                {{"__name__"="kubernetes.io/container/memory/limit_bytes",
                                    "monitored_resource"="k8s_container",
                                    "namespace_name"="{object.namespace}",
                                    "pod_name"=~"{pods_selector}",
                                    "container_name"="{object.container}"{cluster_label}
                                }}
                            ) by (pod_name, container_name, job)
                            
                            * on(pod_name, container_name, job) group_left()
                            
                            max(
                                {{"__name__"="kubernetes.io/container/restart_count",
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
            "GCP OOM detection query (inference-based using restart_count + memory limit) for %s/%s/%s:",
            object.namespace,
            object.name,
            object.container,
        )
        logger.debug("Query:\n%s", query.strip())
        return query
