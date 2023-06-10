from robusta_krr.core.models.allocations import ResourceType
from robusta_krr.core.models.objects import K8sObjectData

from .base_filtered_metric import BaseFilteredMetricLoader
from .base_metric import bind_metric


@bind_metric(ResourceType.Memory)
class MemoryMetricLoader(BaseFilteredMetricLoader):
    def get_query(self, object: K8sObjectData) -> str:
        if len(object.pods) < 300:
            pods_selector = "|".join(pod.name for pod in object.pods)
        else:
            pods_selector = "|".join(set([pod.name[:pod.name.rfind('-')] + '-[0-9a-z]{5}' for pod in object.pods]))
        return (
            "sum(container_memory_working_set_bytes{"
            f'namespace="{object.namespace}", '
            f'pod=~"{pods_selector}", '
            f'container="{object.container}"'
            "}) by (container, pod, job)"
        )
