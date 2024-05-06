from __future__ import annotations

import abc
import logging
from typing import Optional, TYPE_CHECKING

from .workload_loader import BaseWorkloadLoader

if TYPE_CHECKING:
    from robusta_krr.core.integrations.prometheus.connector import PrometheusConnector


logger = logging.getLogger("krr")


class BaseClusterLoader(abc.ABC):
    """
    A class that wraps loading data from multiple clusters.
    For example, a centralized prometheus server that can query multiple clusters.
    Or one kubeconfig can define connections to multiple clusters.
    """

    @abc.abstractmethod
    async def list_clusters(self) -> Optional[list[str]]:
        pass

    @abc.abstractmethod
    def get_workload_loader(self, cluster: Optional[str]) -> BaseWorkloadLoader:
        pass

    def try_get_workload_loader(self, cluster: Optional[str]) -> Optional[BaseWorkloadLoader]:
        try:
            return self.get_workload_loader(cluster)
        except Exception as e:
            logger.error(f"Could not connect to cluster {cluster} and will skip it: {e}")
            return None

    @abc.abstractmethod
    def get_prometheus(self, cluster: Optional[str]) -> PrometheusConnector:
        """
        Connect to a Prometheus server and return a PrometheusConnector instance.
        Cluster = None means that prometheus is the only one: either centralized or in-cluster.
        raise prometrix.PrometheusNotFound if Prometheus is not available.
        """

        pass
