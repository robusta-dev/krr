import abc
import logging

from typing import Optional, Union
from robusta_krr.core.integrations.prometheus.connector import PrometheusConnector
from robusta_krr.core.integrations.prometheus.metrics_service.prometheus_metrics_service import PrometheusMetricsService
from robusta_krr.core.models.objects import K8sWorkload, PodData


logger = logging.getLogger("krr")


class BaseWorkloadLoader(abc.ABC):
    """A base class for single cluster workload loaders."""

    @abc.abstractmethod
    async def list_workloads(self) -> list[K8sWorkload]:
        pass


class IListPodsFallback(abc.ABC):
    """This is an interface that a workload loader can implement to have a fallback method to list pods."""

    @abc.abstractmethod
    async def list_pods(self, object: K8sWorkload) -> list[PodData]:
        pass


class BaseClusterLoader(abc.ABC):
    """
    A class that wraps loading data from multiple clusters.
    For example, a centralized prometheus server that can query multiple clusters.
    Or one kubeconfig can define connections to multiple clusters.
    """

    def __init__(self) -> None:
        self._prometheus_connectors: dict[Optional[str], PrometheusConnector] = {}
        self._connector_errors: set[Exception] = set()

    @abc.abstractmethod
    async def list_clusters(self) -> Optional[list[str]]:
        pass

    @abc.abstractmethod
    async def connect_cluster(self, cluster: str) -> BaseWorkloadLoader:
        pass

    def connect_prometheus(self, cluster: Optional[str] = None) -> PrometheusMetricsService:
        """
        Connect to a Prometheus server and return a PrometheusConnector instance.
        Cluster = None means that prometheus is the only one: either centralized or in-cluster.
        """
        
        if cluster not in self._prometheus_connectors:
            self._prometheus_connectors[cluster] = PrometheusConnector(cluster=cluster)

        return self._prometheus_connectors[cluster]
