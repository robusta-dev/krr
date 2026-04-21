"""
CPU metric loaders for GCP Anthos (on-prem Kubernetes managed by Google).

Anthos uses kubernetes.io/anthos/container/* metrics - same structure as GKE
but with 'anthos' in the metric path.
"""

import logging

from robusta_krr.core.models.objects import K8sObjectData
from ...base import PrometheusMetric, QueryType


logger = logging.getLogger("krr")


class AnthosCPULoader(PrometheusMetric):
    """
    Loads CPU usage metrics from GCP Anthos Managed Prometheus.
    
    Anthos uses kubernetes.io/anthos/container/cpu/core_usage_time
    instead of kubernetes.io/container/cpu/core_usage_time
    """
    
    query_type: QueryType = QueryType.QueryRange
    
    def get_query(self, object: K8sObjectData, _duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        query = f"""
            label_replace(
                label_replace(
                    max(
                        rate(
                            {{"__name__"="kubernetes.io/anthos/container/cpu/core_usage_time",
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
            "Anthos CPU usage query for %s/%s/%s:\n%s",
            object.namespace,
            object.name,
            object.container,
            query.strip(),
        )
        return query


def AnthosPercentileCPULoader(percentile: float) -> type[PrometheusMetric]:
    """
    Factory for creating Anthos CPU loaders for specific percentiles.
    
    Usage:
        loader_95 = AnthosPercentileCPULoader(95)
        loader_99 = AnthosPercentileCPULoader(99)
    """
    if not 0 <= percentile <= 100:
        raise ValueError(f"Percentile must be between 0 and 100, got {percentile}")

    class _AnthosPercentileCPULoader(PrometheusMetric):
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
                                    {{"__name__"="kubernetes.io/anthos/container/cpu/core_usage_time",
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
                "Anthos percentile query %.2f%% for %s/%s/%s:\n%s",
                percentile,
                object.namespace,
                object.name,
                object.container,
                query.strip(),
            )
            return query

    return _AnthosPercentileCPULoader


class AnthosCPUAmountLoader(PrometheusMetric):
    """
    Loads CPU amount (count of containers) for Anthos.
    """
    
    def get_query(self, object: K8sObjectData, duration: str, step: str) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods) or ".*"
        cluster_label = self.get_prometheus_cluster_label()
        query = f"""
            label_replace(
                label_replace(
                    count_over_time(
                        max(
                            {{"__name__"="kubernetes.io/anthos/container/cpu/core_usage_time",
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
            "Anthos CPU amount query for %s/%s/%s:\n%s",
            object.namespace,
            object.name,
            object.container,
            query.strip(),
        )
        return query
