from robusta_krr.core.models.allocations import ResourceType

from .base_metric import bind_metric
from .base_filtered_metric import BaseFilteredMetricLoader


@bind_metric(ResourceType.Memory)
class MemoryMetricLoader(BaseFilteredMetricLoader):
    def get_query(self, namespace: str, pod: str, container: str) -> str:
        return f'sum(container_memory_working_set_bytes{{image!="", namespace="{namespace}", pod="{pod}", container="{container}"}}) by (container, pod, job)'
