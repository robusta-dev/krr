import asyncio
import itertools
import logging

from collections import Counter

from pyparsing import Optional


from robusta_krr.core.integrations.prometheus.connector import PrometheusConnector
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import K8sWorkload
from ..base import BaseWorkloadLoader, BaseClusterLoader
from .loaders import BaseKindLoader, DoubleParentLoader, SimpleParentLoader


logger = logging.getLogger("krr")


class PrometheusClusterLoader(BaseClusterLoader):
    # NOTE: For PrometheusClusterLoader we have to first connect to Prometheus, as we query all data from it

    def __init__(self) -> None:
        super().__init__()
        self.prometheus_connector = super().connect_prometheus()

    async def list_clusters(self) -> list[str]:
        return []
    
    async def connect_cluster(self, cluster: str) -> BaseWorkloadLoader:
        return PrometheusWorkloadLoader(cluster, self.prometheus_connector)
    
    def connect_prometheus(self, cluster: Optional[str] = None) -> PrometheusConnector:
        # NOTE: With prometheus workload loader we can only have one Prometheus provided in parameters
        # so in case of multiple clusters in one Prometheus (centralized version)
        # for each cluster we will have the same PrometheusConnector (keyed by None)
        return self.prometheus_connector

class PrometheusWorkloadLoader(BaseWorkloadLoader):
    workloads: list[type[BaseKindLoader]] = [DoubleParentLoader, SimpleParentLoader]

    def __init__(self, cluster: str, prometheus_connector: PrometheusConnector) -> None:
        self.cluster = cluster
        self.metric_service = prometheus_connector
        self.loaders = [loader(prometheus_connector) for loader in self.workloads]

    async def list_workloads(self) -> list[K8sWorkload]:
        workloads = list(
            itertools.chain(
                *await asyncio.gather(*[loader.list_workloads(settings.namespaces) for loader in self.loaders])
            )
        )

        kind_counts = Counter([workload.kind for workload in workloads])
        for kind, count in kind_counts.items():
            logger.info(f"Found {count} {kind} in {self.cluster}")

        return workloads
