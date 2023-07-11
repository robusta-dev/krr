from typing import Optional

from robusta_krr.core.models.allocations import ResourceType
from robusta_krr.core.models.objects import K8sObjectData

from .base_filtered_metric import BaseFilteredMetricLoader
from .base_metric import QueryType, bind_metric


@bind_metric(ResourceType.CPU)
class CPUMetricLoader(BaseFilteredMetricLoader):
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

    def get_query_type(self) -> QueryType:
        return QueryType.QueryRange
