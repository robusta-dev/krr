import asyncio
import itertools
import logging


from robusta_krr.core.integrations.prometheus.loader import PrometheusMetricsLoader
from robusta_krr.core.models.config import settings
from robusta_krr.core.integrations.prometheus.metrics_service.prometheus_metrics_service import PrometheusMetricsService
from robusta_krr.core.models.objects import K8sWorkload, PodData
from ..base import BaseWorkloadLoader
from .loaders import BaseKindLoader, DeploymentLoader


logger = logging.getLogger("krr")


class PrometheusWorkloadLoader(BaseWorkloadLoader):
    workloads: list[type[BaseKindLoader]] = [DeploymentLoader]

    def __init__(self, cluster: str, metric_loader: PrometheusMetricsLoader) -> None:
        self.cluster = cluster
        self.metric_service = metric_loader
        self.loaders = [loader(metric_loader) for loader in self.workloads]

    async def list_workloads(self) -> list[K8sWorkload]:
        return itertools.chain(await asyncio.gather(*[loader.list_workloads(settings.namespaces, "") for loader in self.loaders]))

    async def list_pods(self, object: K8sWorkload) -> list[PodData]:
        # This should not be implemented, as implementation will repeat PrometheusMetricsLoader.load_pods
        # As this method is ment to be a fallback, repeating the same logic will not be beneficial
        raise NotImplementedError
