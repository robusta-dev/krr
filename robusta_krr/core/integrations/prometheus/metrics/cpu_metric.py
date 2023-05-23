from robusta_krr.core.models.allocations import ResourceType

from .base_metric import bind_metric
from .base_filtered_metric import BaseFilteredMetricLoader
from robusta_krr.core.models.objects import K8sObjectData


@bind_metric(ResourceType.CPU)
class CPUMetricLoader(BaseFilteredMetricLoader):
    def get_query(self, object: K8sObjectData) -> str:
        pods_selector = "|".join(pod.name for pod in object.pods)
        return (
            'sum(irate(container_cpu_usage_seconds_total{'
            f'namespace="{object.namespace}", '
            f'pod=~"{pods_selector}", '
            f'container="{object.container}"'
            '}[5m])) by (container, pod, job)'
        )
