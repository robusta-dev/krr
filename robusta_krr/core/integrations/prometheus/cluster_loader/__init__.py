from __future__ import annotations

import asyncio
import itertools
import logging

from collections import Counter, defaultdict

from typing import Optional
from functools import cache

from robusta_krr.core.integrations.prometheus.connector import PrometheusConnector
from robusta_krr.core.integrations.prometheus.metrics.base import PrometheusMetric
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import HPAData, HPAKey, K8sWorkload
from robusta_krr.core.abstract.workload_loader import BaseWorkloadLoader
from robusta_krr.core.abstract.cluster_loader import BaseClusterLoader
from robusta_krr.core.models.exceptions import CriticalRunnerException
from .loaders import BaseKindLoader, DoubleParentLoader, SimpleParentLoader


logger = logging.getLogger("krr")


class PrometheusClusterLoader(BaseClusterLoader):
    # NOTE: For PrometheusClusterLoader we have to first connect to Prometheus, as we query all data from it

    def __init__(self) -> None:
        self.prometheus = PrometheusConnector()
        if not settings.prometheus_url:
            raise CriticalRunnerException(
                "Prometheus URL is not provided. "
                "Can not auto-discover Prometheus with `--mode prometheus`. "
                "Please provide the URL with `--prometheus-url` flag."
            )

        self.prometheus.connect(settings.prometheus_url)

    async def list_clusters(self) -> Optional[list[str]]:
        if settings.prometheus_label is None:
            logger.info("Assuming that Prometheus contains only one cluster.")
            logger.info("If you have multiple clusters in Prometheus, please provide the `-l` flag.")
            return None

        clusters = await self.prometheus.loader.query(
            f"""
                avg by({settings.prometheus_label}) (
                    kube_pod_container_resource_limits
                )
            """
        )

        return [cluster["metric"][settings.prometheus_label] for cluster in clusters]

    @cache
    def get_workload_loader(self, cluster: str) -> PrometheusWorkloadLoader:
        return PrometheusWorkloadLoader(cluster, self.prometheus)

    def get_prometheus(self, cluster: Optional[str]) -> PrometheusConnector:
        # NOTE: With prometheus workload loader we can only have one Prometheus provided in parameters
        # so in case of multiple clusters in one Prometheus (centralized version)
        # for each cluster we will have the same PrometheusConnector (keyed by None)
        return self.prometheus


class PrometheusWorkloadLoader(BaseWorkloadLoader):
    workloads: list[type[BaseKindLoader]] = [DoubleParentLoader, SimpleParentLoader]

    def __init__(self, cluster: str, prometheus: PrometheusConnector) -> None:
        self.cluster = cluster
        self.prometheus = prometheus
        self.loaders = [loader(cluster, prometheus) for loader in self.workloads]

    async def list_workloads(self) -> list[K8sWorkload]:
        workloads = list(
            itertools.chain(
                *await asyncio.gather(*[loader.list_workloads(settings.namespaces) for loader in self.loaders])
            )
        )

        hpas = await self.__list_hpa()

        for workload in workloads:
            workload.hpa = hpas.get(
                HPAKey(
                    namespace=workload.namespace,
                    kind=workload.kind,
                    name=workload.name,
                )
            )

        kind_counts = Counter([workload.kind for workload in workloads])
        for kind, count in kind_counts.items():
            logger.info(f"Found {count} {kind} in {self.cluster}")

        return workloads

    async def __list_hpa(self) -> dict[HPAKey, HPAData]:
        cluster_selector = f"{settings.prometheus_label}={self.cluster}" if settings.prometheus_label else ""

        hpa_metrics, max_replicas, min_replicas, target_metrics = await asyncio.gather(
            self.prometheus.loader.query("kube_horizontalpodautoscaler_info" + cluster_selector),
            self.prometheus.loader.query("kube_horizontalpodautoscaler_spec_max_replicas" + cluster_selector),
            self.prometheus.loader.query("kube_horizontalpodautoscaler_spec_min_replicas" + cluster_selector),
            self.prometheus.loader.query("kube_horizontalpodautoscaler_spec_target_metric" + cluster_selector),
        )

        max_replicas_dict = {
            (metric["metric"]["namespace"], metric["metric"]["horizontalpodautoscaler"]): metric["value"][1]
            for metric in max_replicas
        }
        min_replicas_dict = {
            (metric["metric"]["namespace"], metric["metric"]["horizontalpodautoscaler"]): metric["value"][1]
            for metric in min_replicas
        }
        target_metric_dict = defaultdict(dict)
        for metric in target_metrics:
            target_metric_dict[(metric["metric"]["namespace"], metric["metric"]["horizontalpodautoscaler"])] |= {
                metric["metric"]["metric_name"]: metric["value"][1]
            }

        hpas = {}
        if not hpa_metrics:
            return {}

        for hpa in hpa_metrics:
            metric = hpa["metric"]
            hpa_name = metric["horizontalpodautoscaler"]
            key = HPAKey(
                namespace=metric["namespace"],
                kind=metric["scaletargetref_kind"],
                name=metric["scaletargetref_name"],
            )

            max_replicas_value = max_replicas_dict[metric["namespace"], hpa_name]
            min_replicas_value = min_replicas_dict[metric["namespace"], hpa_name]
            cpu_utilization = target_metric_dict[metric["namespace"], hpa_name].get("cpu")
            memory_utilization = target_metric_dict[metric["namespace"], hpa_name].get("memory")

            hpas[key] = HPAData(
                min_replicas=max_replicas_value,
                max_replicas=min_replicas_value,
                target_cpu_utilization_percentage=cpu_utilization,
                target_memory_utilization_percentage=memory_utilization,
            )

        return hpas


__all__ = ["PrometheusClusterLoader", "PrometheusWorkloadLoader"]
