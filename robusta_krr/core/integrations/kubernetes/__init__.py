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

from robusta_krr.core.integrations.prometheus.loader import PrometheusMetricsLoader
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import HPAData, K8sWorkload, KindLiteral, PodData
from robusta_krr.core.models.result import ResourceAllocations
from robusta_krr.utils.object_like_dict import ObjectLikeDict
from prometrix import PrometheusNotFound

from . import config_patch as _
from .workload_loader import BaseWorkloadLoader, KubeAPIWorkloadLoader, PrometheusWorkloadLoader

logger = logging.getLogger("krr")

AnyKubernetesAPIObject = Union[V1Deployment, V1DaemonSet, V1StatefulSet, V1Pod, V1Job]
HPAKey = tuple[str, str, str]


class ClusterConnector:
    EXPECTED_EXCEPTIONS = (KeyboardInterrupt, PrometheusNotFound)

    def __init__(self) -> None:
        self._metrics_service_loaders: dict[Optional[str], Union[PrometheusMetricsLoader, Exception]] = {}
        self._metrics_service_loaders_error_logged: set[Exception] = set()

    async def list_clusters(self) -> Optional[list[str]]:
        """List all clusters.

        Returns:
            A list of clusters.
        """

        if settings.inside_cluster:
            logger.debug("Working inside the cluster")
            return None

        try:
            contexts, current_context = config.list_kube_config_contexts(settings.kubeconfig)
        except config.ConfigException:
            if settings.clusters is not None and settings.clusters != "*":
                logger.warning("Could not load context from kubeconfig.")
                logger.warning(f"Falling back to clusters from CLI: {settings.clusters}")
                return settings.clusters
            else:
                logger.error(
                    "Could not load context from kubeconfig. "
                    "Please check your kubeconfig file or pass -c flag with the context name."
                )
            return None

        logger.debug(f"Found {len(contexts)} clusters: {', '.join([context['name'] for context in contexts])}")
        logger.debug(f"Current cluster: {current_context['name']}")

        logger.debug(f"Configured clusters: {settings.clusters}")

        # None, empty means current cluster
        if not settings.clusters:
            return [current_context["name"]]

        # * means all clusters
        if settings.clusters == "*":
            return [context["name"] for context in contexts]

        return [context["name"] for context in contexts if context["name"] in settings.clusters]
    
    def get_prometheus_loader(self, cluster: Optional[str]) -> Optional[PrometheusMetricsLoader]:
        if cluster not in self._metrics_service_loaders:
            try:
                self._metrics_service_loaders[cluster] = PrometheusMetricsLoader(cluster=cluster)
            except Exception as e:
                self._metrics_service_loaders[cluster] = e

        result = self._metrics_service_loaders[cluster]
        if isinstance(result, self.EXPECTED_EXCEPTIONS):
            if result not in self._metrics_service_loaders_error_logged:
                self._metrics_service_loaders_error_logged.add(result)
                logger.error(str(result))
            return None
        elif isinstance(result, Exception):
            raise result

        return result

    def _try_create_cluster_loader(self, cluster: Optional[str]) -> Optional[BaseWorkloadLoader]:
        try:
            if settings.workload_loader == "kubeapi":
                return KubeAPIWorkloadLoader(cluster=cluster)
            elif settings.workload_loader == "prometheus":
                cluster_loader = self.get_prometheus_loader(cluster)
                if cluster_loader is not None:
                    return PrometheusWorkloadLoader(cluster=cluster, metric_loader=cluster_loader)
                else:
                    logger.error(
                        f"Could not load Prometheus for cluster {cluster} and will skip it." 
                        "Not possible to load workloads through Prometheus without connection to Prometheus."
                    )
            else:
                raise NotImplementedError(f"Workload loader {settings.workload_loader} is not implemented")
        except Exception as e:
            logger.error(f"Could not load cluster {cluster} and will skip it: {e}")

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
            return

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
