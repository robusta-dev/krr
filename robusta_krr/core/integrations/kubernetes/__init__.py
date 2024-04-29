import asyncio
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Iterable, Optional, Union

from kubernetes import client, config  # type: ignore
from kubernetes.client import ApiException
from kubernetes.client.models import (
    V1Container,
    V1DaemonSet,
    V1Deployment,
    V1Job,
    V1Pod,
    V1PodList,
    V1StatefulSet,
    V2HorizontalPodAutoscaler,
)

from robusta_krr.core.integrations.prometheus.connector import PrometheusConnector
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import HPAData, K8sWorkload, KindLiteral, PodData
from robusta_krr.core.models.result import ResourceAllocations
from robusta_krr.utils.object_like_dict import ObjectLikeDict
from prometrix import PrometheusNotFound

from . import config_patch as _
from .workload_loader import (
    BaseWorkloadLoader,
    PrometheusWorkloadLoader,
    BaseClusterLoader,
    KubeAPIClusterLoader,
    PrometheusClusterLoader,
)

logger = logging.getLogger("krr")

AnyKubernetesAPIObject = Union[V1Deployment, V1DaemonSet, V1StatefulSet, V1Pod, V1Job]
HPAKey = tuple[str, str, str]


class ClusterConnector:
    EXPECTED_EXCEPTIONS = (KeyboardInterrupt, PrometheusNotFound)

    def __init__(self) -> None:
        self._prometheus_connectors: dict[Optional[str], Union[PrometheusConnector, Exception]] = {}
        self._connector_errors: set[Exception] = set()

    def get_prometheus(self, cluster: Optional[str]) -> Optional[PrometheusConnector]:
        if settings.workload_loader == "kubeapi":
            logger.debug(f"Creating Prometheus connector for cluster {cluster}")
        elif settings.workload_loader == "prometheus":
            logger.debug(f"Creating Prometheus connector")
            # NOTE: With prometheus workload loader we can only have one Prometheus provided in parameters
            # so in case of multiple clusters in one Prometheus (centralized version) 
            # for each cluster we will have the same PrometheusConnector (keyed by None)
            cluster = None

        

    def _create_cluster_loader(self) -> BaseClusterLoader:
        try:

        except Exception as e:
            logger.error(f"Could not connect to cluster loader and will skip it: {e}")

        return None

    async def list_workloads(self, clusters: Optional[list[str]]) -> list[K8sWorkload]:
        """List all scannable objects.

        Returns:
            A list of all loaded objects.
        """

        if clusters is None:
            _cluster_loaders = [self._try_create_cluster_loader(None)]
        else:
            _cluster_loaders = [self._try_create_cluster_loader(cluster) for cluster in clusters]

        self.cluster_loaders: dict[Optional[str], BaseWorkloadLoader] = {
            cl.cluster: cl for cl in _cluster_loaders if cl is not None
        }

        if self.cluster_loaders == {}:
            logger.error("Could not load any cluster.")
            return []

        return [
            object
            for cluster_loader in self.cluster_loaders.values()
            for object in await cluster_loader.list_workloads()
        ]

    async def load_pods(self, object: K8sWorkload) -> list[PodData]:
        try:
            cluster_loader = self.cluster_loaders[object.cluster]
        except KeyError:
            raise RuntimeError(f"Cluster loader for cluster {object.cluster} not found") from None

        return await cluster_loader.list_pods(object)
