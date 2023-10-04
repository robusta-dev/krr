from __future__ import annotations

import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Optional

from kubernetes import config as k8s_config
from kubernetes.client.api_client import ApiClient
from prometrix import MetricsNotFound, PrometheusNotFound

from robusta_krr.core.models.objects import K8sObjectData, PodData
from robusta_krr.utils.configurable import Configurable

from .metrics_service.prometheus_metrics_service import PrometheusMetricsService
from .metrics_service.thanos_metrics_service import ThanosMetricsService
from .metrics_service.victoria_metrics_service import VictoriaMetricsService

if TYPE_CHECKING:
    from robusta_krr.core.abstract.strategies import BaseStrategy, MetricsPodData
    from robusta_krr.core.models.config import Config

METRICS_SERVICES = {
    "Prometheus": PrometheusMetricsService,
    "Victoria Metrics": VictoriaMetricsService,
    "Thanos": ThanosMetricsService,
}


class PrometheusMetricsLoader(Configurable):
    def __init__(
        self,
        config: Config,
        *,
        cluster: Optional[str] = None,
    ) -> None:
        """
        Initializes the Prometheus Loader.

        Args:
            config (Config): The configuration object.
            cluster (Optional[str]): The name of the cluster. Defaults to None.
        """

        super().__init__(config=config)

        self.executor = ThreadPoolExecutor(self.config.max_workers)

        self.api_client = (
            k8s_config.new_client_from_config(config_file=self.config.kubeconfig, context=cluster)
            if cluster is not None
            else None
        )
        loader = self.get_metrics_service(config, api_client=self.api_client, cluster=cluster)
        if loader is None:
            raise PrometheusNotFound("No Prometheus or metrics service found")

        self.loader = loader

        self.info(f"{self.loader.name} connected successfully for {cluster or 'default'} cluster")

    def get_metrics_service(
        self,
        config: Config,
        api_client: Optional[ApiClient] = None,
        cluster: Optional[str] = None,
    ) -> Optional[PrometheusMetricsService]:
        for service_name, metric_service_class in METRICS_SERVICES.items():
            try:
                loader = metric_service_class(config, api_client=api_client, cluster=cluster, executor=self.executor)
                loader.check_connection()
                self.echo(f"{service_name} found")
                loader.validate_cluster_name()
                return loader
            except MetricsNotFound as e:
                self.debug(f"{service_name} not found: {e}")

        return None

    async def load_pods(self, object: K8sObjectData, period: datetime.timedelta) -> list[PodData]:
        return await self.loader.load_pods(object, period)

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
