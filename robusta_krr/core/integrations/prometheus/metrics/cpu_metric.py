from robusta_krr.core.models.allocations import ResourceType

from .base_metric import BaseMetricLoader, bind_metric


@bind_metric(ResourceType.CPU)
class CPUMetricLoader(BaseMetricLoader):
    def get_query(self, namespace: str, pod: str, container: str) -> str:
        return f'sum(irate(container_cpu_usage_seconds_total{{namespace="{namespace}", pod="{pod}", container="{container}"}}[5m])) by (container, pod, job)'
