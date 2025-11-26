"""
GCP Managed Prometheus CPU metric loaders.

These loaders use GCP's kubernetes.io/container/cpu/core_usage_time metric
with UTF-8 PromQL syntax required by GCP Managed Prometheus.
"""

import logging

from robusta_krr.core.models.objects import K8sObjectData

from ..base import PrometheusMetric, QueryType


logger = logging.getLogger("krr")


class GcpCPULoader(PrometheusMetric):
    """
    A metric loader for loading CPU usage metrics from GCP Managed Prometheus.
    Uses kubernetes.io/container/cpu/core_usage_time instead of container_cpu_usage_seconds_total.
    """

    query_type: QueryType = QueryType.QueryRange

    def get_query(self, object: K8sObjectData, _duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        
        # GCP requires UTF-8 syntax with quoted metric names and labels
        # Note: GCP uses "monitored_resource"="k8s_container" label
        # We also rename GCP labels (pod_name -> pod, container_name -> container) for compatibility
        query = f"""
            label_replace(
                label_replace(
                    max(
                        rate(
                            {{"__name__"="kubernetes.io/container/cpu/core_usage_time",
                                "monitored_resource"="k8s_container",
                                "namespace_name"="{object.namespace}",
                                "pod_name"=~"{pods_selector}",
                                "container_name"="{object.container}"{cluster_label}
                            }}[{step}]
                        )
                    ) by (container_name, pod_name, job),
                    "pod", "$1", "pod_name", "(.+)"
                ),
                "container", "$1", "container_name", "(.+)"
            )
        """
        logger.debug(
            "GCP CPU usage query for %s/%s/%s:\n%s",
            object.namespace,
            object.name,
            object.container,
            query.strip(),
        )
        return query


def GcpPercentileCPULoader(percentile: float) -> type[PrometheusMetric]:
    """
    A factory for creating percentile CPU usage metric loaders for GCP Managed Prometheus.
    """

    if not 0 <= percentile <= 100:
        raise ValueError("percentile must be between 0 and 100")

    class _GcpPercentileCPULoader(PrometheusMetric):
        # Store percentile as class attribute for later retrieval
        _percentile = percentile
        
        def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
            pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
            cluster_label = self.get_prometheus_cluster_label()
            query = f"""
                label_replace(
                    label_replace(
                        quantile_over_time(
                            {round(percentile / 100, 2)},
                            max(
                                rate(
                                    {{"__name__"="kubernetes.io/container/cpu/core_usage_time",
                                        "monitored_resource"="k8s_container",
                                        "namespace_name"="{object.namespace}",
                                        "pod_name"=~"{pods_selector}",
                                        "container_name"="{object.container}"{cluster_label}
                                    }}[{step}]
                                )
                            ) by (container_name, pod_name, job)
                            [{duration}:{step}]
                        ),
                        "pod", "$1", "pod_name", "(.+)"
                    ),
                    "container", "$1", "container_name", "(.+)"
                )
            """
            logger.debug(
                "GCP percentile query %.2f%% for %s/%s/%s:\n%s",
                percentile,
                object.namespace,
                object.name,
                object.container,
                query.strip(),
            )
            return query
    
    # Set user-friendly names for logging
    _GcpPercentileCPULoader.__name__ = "PercentileCPULoader"
    _GcpPercentileCPULoader.__qualname__ = "PercentileCPULoader"
    return _GcpPercentileCPULoader


class GcpCPUAmountLoader(PrometheusMetric):
    """
    A metric loader for loading CPU data points count from GCP Managed Prometheus.
    """

    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        query = f"""
            label_replace(
                label_replace(
                    count_over_time(
                        max(
                            {{"__name__"="kubernetes.io/container/cpu/core_usage_time",
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
            "GCP CPU amount query for %s/%s/%s:\n%s",
            object.namespace,
            object.name,
            object.container,
            query.strip(),
        )
        return query
