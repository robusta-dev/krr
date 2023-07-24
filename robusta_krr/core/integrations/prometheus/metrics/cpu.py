from typing import Optional

from robusta_krr.core.models.objects import K8sObjectData

from .base import QueryMetric, QueryRangeMetric, FilterMetric


class CPULoader(QueryRangeMetric, FilterMetric):
    def get_query(self, object: K8sObjectData, resolution: Optional[str]) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return (
            "sum(irate(container_cpu_usage_seconds_total{"
            f'namespace="{object.namespace}", '
            f'pod=~"{pods_selector}", '
            f'container="{object.container}"'
            f"{cluster_label}"
            "}[5m])) by (container, pod, job)"
        )


class MaxCPULoader(QueryMetric, FilterMetric):
    def get_query(self, object: K8sObjectData, resolution: Optional[str]) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return (
            "sum(irate(container_cpu_usage_seconds_total{"
            f'namespace="{object.namespace}", '
            f'pod=~"{pods_selector}", '
            f'container="{object.container}"'
            f"{cluster_label}"
            "}[5m])) by (container, pod, job)"
        )
