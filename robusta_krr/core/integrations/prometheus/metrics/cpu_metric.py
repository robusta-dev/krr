from robusta_krr.core.models.allocations import ResourceType
from robusta_krr.core.models.objects import K8sObjectData

from .base_filtered_metric import BaseFilteredMetricLoader
from .base_metric import bind_metric


@bind_metric(ResourceType.CPU)
class CPUMetricLoader(BaseFilteredMetricLoader):
    def get_query(self, object: K8sObjectData) -> str:
        if len(object.pods) < 300:
            pods_selector = "|".join(pod.name for pod in object.pods)
        else:
            pods_selector = "|".join(set([pod.name[:pod.name.rfind('-')] + '-[0-9a-z]{5}' for pod in object.pods]))
        cluster_label = self.get_prometheus_cluster_label()
        return (
            "sum(irate(container_cpu_usage_seconds_total{"
            f'namespace="{object.namespace}", '
            f'pod=~"{pods_selector}", '
            f'container="{object.container}"'
            f"{cluster_label}"
            "}[5m])) by (container, pod, job)"
        )
