import asyncio
import itertools
import logging

from collections import Counter


from robusta_krr.core.integrations.prometheus.connector import PrometheusConnector
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import K8sWorkload
from ..base import BaseWorkloadLoader
from .loaders import BaseKindLoader, DoubleParentLoader, SimpleParentLoader


logger = logging.getLogger("krr")


class PrometheusWorkloadLoader(BaseWorkloadLoader):
    workloads: list[type[BaseKindLoader]] = [DoubleParentLoader, SimpleParentLoader]

    def __init__(self, cluster: str, metric_loader: PrometheusConnector) -> None:
        self.cluster = cluster
        self.metric_service = metric_loader
        self.loaders = [loader(metric_loader) for loader in self.workloads]

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
