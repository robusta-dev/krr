"""
GCP Managed Prometheus metrics service.

This service extends PrometheusMetricsService to use GCP-specific metric loaders
that work with GCP's kubernetes.io/* metric naming conventions.
"""

import logging
from datetime import timedelta
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from kubernetes.client import ApiClient
from prometrix import MetricsNotFound

from robusta_krr.core.abstract.strategies import PodsTimeData
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.utils.service_discovery import MetricsServiceDiscovery

from ..metrics import PrometheusMetric
from ..metrics.gcp import (
    GcpCPULoader,
    GcpPercentileCPULoader,
    GcpCPUAmountLoader,
    GcpMemoryLoader,
    GcpMaxMemoryLoader,
    GcpMemoryAmountLoader,
)
from .prometheus_metrics_service import PrometheusMetricsService

logger = logging.getLogger("krr")


class GcpManagedPrometheusDiscovery(MetricsServiceDiscovery):
    """
    Discovery service for GCP Managed Prometheus.
    
    GCP Managed Prometheus is typically accessed via a direct URL rather than
    Kubernetes service discovery, but this class is provided for consistency.
    """
    
    def find_metrics_url(self, *, api_client: Optional[ApiClient] = None) -> Optional[str]:
        """
        GCP Managed Prometheus is typically accessed via a known URL pattern:
        https://monitoring.googleapis.com/v1/projects/{project_id}/location/global/prometheus
        
        This method returns None to indicate that auto-discovery is not supported.
        Users should provide the URL explicitly via --prometheus-url flag.
        """
        logger.debug("GCP Managed Prometheus auto-discovery not supported. Use --prometheus-url flag.")
        return None


class GcpManagedPrometheusMetricsService(PrometheusMetricsService):
    """
    A metrics service for GCP Managed Prometheus.
    
    This service automatically uses GCP-specific metric loaders that query
    kubernetes.io/container/cpu/core_usage_time and kubernetes.io/container/memory/used_bytes
    instead of standard Prometheus metrics.
    
    It also handles GCP's UTF-8 PromQL syntax requirements.
    """

    service_discovery = GcpManagedPrometheusDiscovery

    # Mapping from standard Prometheus loaders to GCP equivalents
    LOADER_MAPPING = {
        "CPULoader": GcpCPULoader,
        "PercentileCPULoader": GcpPercentileCPULoader,
        "CPUAmountLoader": GcpCPUAmountLoader,
        "MemoryLoader": GcpMemoryLoader,
        "MaxMemoryLoader": GcpMaxMemoryLoader,
        "MemoryAmountLoader": GcpMemoryAmountLoader,
        "MaxOOMKilledMemoryLoader": None,  # Not supported on GCP (requires kube-state-metrics)
    }

    def __init__(
        self,
        *,
        cluster: Optional[str] = None,
        api_client: Optional[ApiClient] = None,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        logger.info("Initializing GCP Managed Prometheus metrics service")
        super().__init__(cluster=cluster, api_client=api_client, executor=executor)
        logger.info(f"GCP Managed Prometheus service initialized for cluster {cluster or 'default'}")
        logger.info(f"Using GCP metric naming: kubernetes.io/container/cpu/core_usage_time and kubernetes.io/container/memory/used_bytes")

    def check_connection(self):
        """
        Checks the connection to GCP Managed Prometheus.
        
        Raises:
            MetricsNotFound: If the connection cannot be established.
        """
        try:
            super().check_connection()
            logger.info("Successfully connected to GCP Managed Prometheus")
        except MetricsNotFound as e:
            raise MetricsNotFound(
                f"Couldn't connect to GCP Managed Prometheus at {self.url}\n"
                f"Make sure you have:\n"
                f"  1. The correct project ID and cluster name in the URL\n"
                f"  2. Valid authentication credentials (gcloud auth print-access-token)\n"
                f"  3. The Managed Service for Prometheus enabled in your GCP project\n"
                f"Caused by {e.__class__.__name__}: {e}"
            ) from e

    async def gather_data(
        self,
        object: K8sObjectData,
        LoaderClass: type[PrometheusMetric],
        period: timedelta,
        step: timedelta = timedelta(minutes=30),
    ) -> PodsTimeData:
        """
        Gathers data using GCP-specific metric loaders.
        
        This method intercepts the loader class and replaces it with the GCP equivalent
        if a mapping exists. This allows strategies to continue using standard loader names
        while automatically querying GCP metrics.
        """
        loader_name = LoaderClass.__name__
        
        # Handle PercentileCPULoader factory pattern specially
        if loader_name == "PercentileCPULoader":
            # Extract percentile from the loader class attribute (set by factory)
            percentile = getattr(LoaderClass, '_percentile', 95)
            logger.debug(f"Detected PercentileCPULoader with percentile={percentile}, creating GCP equivalent")
            GcpLoaderClass = GcpPercentileCPULoader(percentile)
        elif loader_name in self.LOADER_MAPPING:
            GcpLoaderClass = self.LOADER_MAPPING[loader_name]
            
            # Handle unsupported loaders (e.g., MaxOOMKilledMemoryLoader)
            if GcpLoaderClass is None:
                logger.warning(
                    f"{loader_name} is not supported on GCP Managed Prometheus. "
                    f"This metric requires kube-state-metrics which may not be available. "
                    f"Returning empty data."
                )
                return {}
                
            logger.debug(f"Mapping {loader_name} to GCP equivalent")
        else:
            # No mapping found, use the original loader (may fail with GCP metrics)
            logger.warning(
                f"No GCP mapping found for {loader_name}. "
                f"This loader may not work with GCP Managed Prometheus."
            )
            GcpLoaderClass = LoaderClass
        
        # Call the parent method with the GCP loader
        return await super().gather_data(object, GcpLoaderClass, period, step)

    @classmethod
    def name(cls) -> str:
        """Return a user-friendly name for this service."""
        return "GCP Managed Prometheus"

    async def get_cluster_summary(self) -> Dict[str, Any]:
        """
        Get cluster summary for GCP Managed Prometheus.
        
        GCP Managed Prometheus does not have machine_* or kube_pod_container_resource_requests metrics
        by default, so we return an empty dict. This is not critical for recommendations.
        """
        logger.info("Skipping cluster summary for GCP Managed Prometheus (metrics not available)")
        logger.info("This does not affect resource recommendations, only cluster-wide statistics")
        return {}
