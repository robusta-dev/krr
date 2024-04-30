from __future__ import annotations

import asyncio
import itertools
import logging

from collections import Counter

from typing import Optional
from functools import cache

from robusta_krr.core.integrations.prometheus.connector import PrometheusConnector
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import K8sWorkload
from robusta_krr.core.abstract.workload_loader import BaseWorkloadLoader
from robusta_krr.core.abstract.cluster_loader import BaseClusterLoader
from robusta_krr.core.models.exceptions import CriticalRunnerException
from .loaders import BaseKindLoader, DoubleParentLoader, SimpleParentLoader


logger = logging.getLogger("krr")


class PrometheusClusterLoader(BaseClusterLoader):
    # NOTE: For PrometheusClusterLoader we have to first connect to Prometheus, as we query all data from it

    def __init__(self) -> None:
        self._prometheus_connector = PrometheusConnector()
        if not settings.prometheus_url:
            raise CriticalRunnerException(
                "Prometheus URL is not provided. "
                "Can not auto-discover Prometheus with `--mode prometheus`. "
                "Please provide the URL with `--prometheus-url` flag."
            )

        self._prometheus_connector.connect(settings.prometheus_url)

    async def list_clusters(self) -> Optional[list[str]]:
        if settings.prometheus_cluster_label is None:
            return None

        # TODO: We can try to auto-discover clusters by querying Prometheus,
        # but for that we will need to rework PrometheusMetric.get_prometheus_cluster_label
        return [settings.prometheus_cluster_label]

    @cache
    def get_workload_loader(self, cluster: str) -> PrometheusWorkloadLoader:
        return PrometheusWorkloadLoader(cluster, self._prometheus_connector)

    def get_prometheus(self, cluster: Optional[str]) -> PrometheusConnector:
        # NOTE: With prometheus workload loader we can only have one Prometheus provided in parameters
        # so in case of multiple clusters in one Prometheus (centralized version)
        # for each cluster we will have the same PrometheusConnector (keyed by None)
        return self._prometheus_connector


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

__all__ = ["PrometheusClusterLoader", "PrometheusWorkloadLoader"]