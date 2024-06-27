from __future__ import annotations

import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Optional, Dict, Any

from kubernetes import config as k8s_config
from kubernetes.client.api_client import ApiClient
from kubernetes.client.exceptions import ApiException
from prometrix import MetricsNotFound, PrometheusNotFound

from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import K8sObjectData, PodData

from .metrics_service.prometheus_metrics_service import PrometheusMetricsService
from .metrics_service.thanos_metrics_service import ThanosMetricsService
from .metrics_service.victoria_metrics_service import VictoriaMetricsService
from .metrics_service.mimir_metrics_service import MimirMetricsService

if TYPE_CHECKING:
    from robusta_krr.core.abstract.strategies import BaseStrategy, MetricsPodData

logger = logging.getLogger("krr")

class PrometheusMetricsLoader:
    def __init__(self, *, cluster: Optional[str] = None) -> None:
        """
        Initializes the Prometheus Loader.

        Args:
            cluster (Optional[str]): The name of the cluster. Defaults to None.
        """

        self.executor = ThreadPoolExecutor(settings.max_workers)
        self.api_client = settings.get_kube_client(context=cluster)
        loader = self.get_metrics_service(api_client=self.api_client, cluster=cluster)
        if loader is None:
            raise PrometheusNotFound(
                f"Wasn't able to connect to any Prometheus service in {cluster or 'inner'} cluster\n"
                "Try using port-forwarding and/or setting the url manually (using the -p flag.).\n"
                "For more information, see 'Giving the Explicit Prometheus URL' at https://github.com/robusta-dev/krr?tab=readme-ov-file#usage"
            )

        self.loader = loader

        logger.info(f"{self.loader.name()} connected successfully for {cluster or 'default'} cluster")

    def get_metrics_service(
        self,
        api_client: Optional[ApiClient] = None,
        cluster: Optional[str] = None,
    ) -> Optional[PrometheusMetricsService]:
        if settings.prometheus_url is not None:
            logger.info("Prometheus URL is specified, will not auto-detect a metrics service")
            metrics_to_check = [PrometheusMetricsService]
        else:
            logger.info("No Prometheus URL is specified, trying to auto-detect a metrics service")
            metrics_to_check = [VictoriaMetricsService, ThanosMetricsService, MimirMetricsService, PrometheusMetricsService]

        for metric_service_class in metrics_to_check:
            service_name = metric_service_class.name()
            try:
                loader = metric_service_class(api_client=api_client, cluster=cluster, executor=self.executor)
                loader.check_connection()
            except MetricsNotFound as e:
                logger.info(f"{service_name} not found: {e}")
            except ApiException as e:
                logger.warning(
                    f"Unable to automatically discover a {service_name} in the cluster ({e}). "
                    "Try specifying how to connect to Prometheus via cli options"
                )
            else:
                logger.info(f"{service_name} found")
                loader.validate_cluster_name()
                return loader

        return None

    async def get_history_range(
        self, history_duration: datetime.timedelta
    ) -> Optional[tuple[datetime.datetime, datetime.datetime]]:
        return await self.loader.get_history_range(history_duration)

    async def load_pods(self, object: K8sObjectData, period: datetime.timedelta) -> list[PodData]:
        try:
            return await self.loader.load_pods(object, period)
        except Exception as e:
            logger.exception(f"Failed to load pods for {object}: {e}")
            return []

    async def get_cluster_summary(self) -> Dict[str, Any]:
        try:
            return await self.loader.get_cluster_summary()
        except Exception as e:
            logger.exception(f"Failed to get cluster summary: {e}")
            return {}

    async def gather_data(
        self,
        object: K8sObjectData,
        strategy: BaseStrategy,
        period: datetime.timedelta,
        *,
        step: datetime.timedelta = datetime.timedelta(minutes=30),
    ) -> MetricsPodData:
        """
        Gathers data from Prometheus for a specified object and resource.

        Args:
            object (K8sObjectData): The Kubernetes object.
            resource (ResourceType): The resource type.
            period (datetime.timedelta): The time period for which to gather data.
            step (datetime.timedelta, optional): The time step between data points. Defaults to 30 minutes.

        Returns:
            ResourceHistoryData: The gathered resource history data.
        """

        return {
            MetricLoader.__name__: await self.loader.gather_data(object, MetricLoader, period, step)
            for MetricLoader in strategy.metrics
        }
