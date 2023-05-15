from robusta_krr.core.models.allocations import ResourceType

from .base_metric import bind_metric
from .base_filtered_metric import BaseFilteredMetricLoader


@bind_metric(ResourceType.CPU)
class CPUMetricLoader(BaseFilteredMetricLoader):
    def get_query(self, namespace: str, pod: str, container: str) -> str:
        return f'sum(irate(container_cpu_usage_seconds_total{{namespace="{namespace}", pod="{pod}", container="{container}"}}[5m])) by (container, pod, job)'
