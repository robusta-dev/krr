from typing import Optional
from robusta_krr.core.models.allocations import ResourceType
from robusta_krr.core.models.objects import K8sObjectData

from .base_filtered_metric import BaseFilteredMetricLoader
from .base_metric import bind_metric, QueryType, override_metric


@bind_metric(ResourceType.Memory)
class MemoryMetricLoader(BaseFilteredMetricLoader):
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

    def get_query_type(self) -> QueryType:
        return QueryType.QueryRange

# This is a temporary solutions, metric loaders will be moved to strategy in the future
@override_metric("simple", ResourceType.Memory)
class MemoryMetricLoader(MemoryMetricLoader):
    """
    A class that overrides the memory metric on the simple strategy.
    """

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

    def get_query_type(self) -> QueryType:
        return QueryType.Query

    def get_graph_query(self, object: K8sObjectData, resolution: Optional[str]) -> str: 
        return super().get_query(object, resolution)
