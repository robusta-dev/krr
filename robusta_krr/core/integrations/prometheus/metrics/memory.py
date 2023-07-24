from typing import Optional

from robusta_krr.core.models.objects import K8sObjectData

from .base import QueryMetric, QueryRangeMetric, FilterMetric


class MemoryLoader(QueryRangeMetric, FilterMetric):
    def get_query(self, object: K8sObjectData, resolution: Optional[str]) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        return (
            "sum(container_memory_working_set_bytes{"
            f'namespace="{object.namespace}", '
            f'pod=~"{pods_selector}", '
            f'container="{object.container}"'
            f"{cluster_label}"
            "}) by (container, pod, job, id)"
        )


class MaxMemoryLoader(QueryMetric, FilterMetric):
    def get_query(self, object: K8sObjectData, resolution: Optional[str]) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        cluster_label = self.get_prometheus_cluster_label()
        resolution_formatted = f"[{resolution}]" if resolution else ""
        return (
            f"max_over_time(container_memory_working_set_bytes{{"
            f'namespace="{object.namespace}", '
            f'pod=~"{pods_selector}", '
            f'container="{object.container}"'
            f"{cluster_label}}}"
            f"{resolution_formatted}"
            f")"
        )
