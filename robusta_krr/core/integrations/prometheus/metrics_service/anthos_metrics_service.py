"""
Anthos Managed Prometheus metrics service.

Anthos (on-prem Kubernetes managed by Google) uses kubernetes.io/anthos/container/* metrics
instead of standard kubernetes.io/container/* metrics used by GKE.
"""

import logging
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from kubernetes.client import ApiClient

from robusta_krr.core.abstract.strategies import PodsTimeData
from robusta_krr.core.models.objects import K8sObjectData, PodData
from ..metrics import PrometheusMetric
from ..metrics.gcp.anthos import (
    AnthosCPULoader,
    AnthosPercentileCPULoader,
    AnthosCPUAmountLoader,
    AnthosMemoryLoader,
    AnthosMaxMemoryLoader,
    AnthosMemoryAmountLoader,
)
from .gcp_metrics_service import GcpManagedPrometheusMetricsService

logger = logging.getLogger("krr")


class AnthosMetricsService(GcpManagedPrometheusMetricsService):
    """
    Metrics service for GCP Anthos Managed Prometheus.
    
    Anthos uses kubernetes.io/anthos/container/* metrics with the
    monitored_resource="k8s_container" label.
    
    Key differences from GKE:
    - Metric prefix: kubernetes.io/anthos/container/*
    - Additional label: monitored_resource="k8s_container"
    - Memory aggregation: max_over_time instead of max_over_time
    """

    # Loader mapping for Anthos metrics
    LOADER_MAPPING: Dict[str, Optional[type[PrometheusMetric]]] = {
        "CPULoader": AnthosCPULoader,
        "MemoryLoader": AnthosMemoryLoader,
        "MaxMemoryLoader": AnthosMaxMemoryLoader,
        "PercentileCPULoader": AnthosPercentileCPULoader,
        "CPUAmountLoader": AnthosCPUAmountLoader,
        "MemoryAmountLoader": AnthosMemoryAmountLoader,
        # OOM killer metrics not available in Anthos
        "MaxOOMKilledMemoryLoader": None,
    }

    def __init__(
        self,
        *,
        cluster: Optional[str] = None,
        api_client: Optional[ApiClient] = None,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        """
        Initialize Anthos metrics service.
        
        Args:
            cluster: Cluster name or object
            api_client: Kubernetes API client
            executor: Thread pool executor for parallel operations
        """
        logger.info("Initializing Anthos Metrics Service for on-prem Kubernetes managed by GCP")
        super().__init__(cluster=cluster, api_client=api_client, executor=executor)

    async def get_cluster_summary(self) -> Dict[str, Any]:
        """
        Get cluster summary for Anthos.
        
        Anthos does not have machine_* or kube_pod_container_resource_requests metrics
        by default, so we return an empty dict. This is not critical for recommendations.
        """
        logger.info("Anthos: Cluster summary metrics not available. Using Kubernetes API for cluster information instead.")
        return {}

    async def load_pods(self, object: K8sObjectData, period: timedelta) -> List[PodData]:

        """
        Load pods for Anthos.
        
        Anthos Managed Prometheus does not have kube-state-metrics (kube_replicaset_owner, etc.),
        so we always return an empty list. This forces KRR to use Kubernetes API for pod discovery,
        which is the correct approach for Anthos.
        
        The parent class's load_pods() tries to query kube_* metrics which don't exist in Anthos.
        """
        logger.debug(f"Anthos: Using Kubernetes API for pod discovery (kube-state-metrics not available)")
        return []

    async def gather_data(
        self,
        object: K8sObjectData,
        LoaderClass: type[PrometheusMetric],
        period: timedelta,
        step: timedelta = timedelta(minutes=30),
    ) -> PodsTimeData:
        """
        Gathers data using Anthos-specific metric loaders.
        
        This method intercepts the loader class and replaces it with the Anthos equivalent
        if a mapping exists. This allows strategies to continue using standard loader names
        while automatically querying Anthos metrics.
        """
        loader_name = LoaderClass.__name__
        
        # Handle PercentileCPULoader factory pattern specially
        if loader_name == "PercentileCPULoader":
            # Extract percentile from the loader class attribute (set by factory)
            percentile = getattr(LoaderClass, '_percentile', 95)
            if percentile not in self._percentile_log_cache:
                logger.info(
                    "Anthos Managed Prometheus: using CPU percentile %s%% from --cpu-percentile for quantile_over_time queries",
                    percentile,
                )
                self._percentile_log_cache.add(percentile)
            AnthosLoaderClass = AnthosPercentileCPULoader(percentile)
        elif loader_name in self.LOADER_MAPPING:
            AnthosLoaderClass = self.LOADER_MAPPING[loader_name]
            
            # Handle unsupported loaders (e.g., MaxOOMKilledMemoryLoader)
            if AnthosLoaderClass is None:
                logger.warning(
                    f"{loader_name} is not supported on Anthos Managed Prometheus. "
                    f"This metric requires kube-state-metrics which may not be available. "
                    f"Returning empty data."
                )
                return {}
                
            logger.debug(f"Mapping {loader_name} to Anthos equivalent")
        else:
            # No mapping found, use the original loader (may fail with Anthos metrics)
            logger.warning(
                f"No Anthos mapping found for {loader_name}. "
                f"This loader may not work with Anthos Managed Prometheus."
            )
            AnthosLoaderClass = LoaderClass
        
        # Call PrometheusMetricsService.gather_data() directly to bypass GCP's gather_data()
        # This prevents double-mapping: Anthos already mapped to Anthos loaders,
        # we don't want GCP to try mapping them again
        from .prometheus_metrics_service import PrometheusMetricsService
        return await PrometheusMetricsService.gather_data(self, object, AnthosLoaderClass, period, step)
