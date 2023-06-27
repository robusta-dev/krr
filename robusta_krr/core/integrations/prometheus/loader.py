import asyncio
import datetime
from typing import Optional, no_type_check

from concurrent.futures import ThreadPoolExecutor

from kubernetes import config as k8s_config
from kubernetes.client.api_client import ApiClient

from robusta_krr.core.abstract.strategies import ResourceHistoryData
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.core.models.result import ResourceType
from robusta_krr.utils.configurable import Configurable

from .metrics_service.base_metric_service import MetricsNotFound, MetricsService
from .metrics_service.prometheus_metrics_service import PrometheusMetricsService, PrometheusNotFound
from .metrics_service.thanos_metrics_service import ThanosMetricsService
from .metrics_service.victoria_metrics_service import VictoriaMetricsService

METRICS_SERVICES = {
    "Prometheus": PrometheusMetricsService,
    "Victoria Metrics": VictoriaMetricsService,
    "Thanos": ThanosMetricsService,
}


class MetricsLoader(Configurable):
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
        self.loader = self.get_metrics_service(config, api_client=self.api_client, cluster=cluster)
        if not self.loader:
            raise PrometheusNotFound("No Prometheus or metrics service found")

        self.info(f"{self.loader.name()} connected successfully for {cluster or 'default'} cluster")

    def get_metrics_service(
        self,
        config: Config,
        api_client: Optional[ApiClient] = None,
        cluster: Optional[str] = None,
    ) -> Optional[MetricsService]:
        for service_name, metric_service_class in METRICS_SERVICES.items():
            try:
                loader = metric_service_class(config, api_client=api_client, cluster=cluster, executor=self.executor)
                loader.check_connection()
                self.echo(f"{service_name} found")
                loader.validate_cluster_name()
                return loader
            except MetricsNotFound as e:
                self.debug(f"{service_name} not found")

    async def gather_data(
        self,
        object: K8sObjectData,
        resource: ResourceType,
        period: datetime.timedelta,
        *,
        step: datetime.timedelta = datetime.timedelta(minutes=30),
    ) -> ResourceHistoryData:
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

        return await self.loader.gather_data(object, resource, period, step)
