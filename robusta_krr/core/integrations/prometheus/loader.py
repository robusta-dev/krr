import asyncio
import datetime
from typing import Optional, no_type_check

from kubernetes import config as k8s_config

from robusta_krr.core.abstract.strategies import ResourceHistoryData
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.core.models.result import ResourceType
from robusta_krr.utils.configurable import Configurable
from .metrics_service.prometheus_metrics_service import PrometheusMetricsService
from .metrics_service.victoria_metrics_service import VictoriaMetricsService
from .metrics_service.base_metric_service import MetricsService
from kubernetes.client.api_client import ApiClient

METRICS_SERVICES = {
    "Prometheus": PrometheusMetricsService,
    "Victoria Metrics": VictoriaMetricsService,
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

        self.api_client = k8s_config.new_client_from_config(context=cluster) if cluster is not None else None
        self.loader = self.get_metrics_service(config, api_client=self.api_client, cluster=cluster)
        self.loader.check_connection()

        self.info(f"Prometheus connected successfully for {cluster or 'default'} cluster")


    def get_metrics_service(self,
            config: Config,
            api_client: Optional[ApiClient] = None,
            cluster: Optional[str] = None,) -> Optional[MetricsService]:
        
        for service_name, metric_service_class in METRICS_SERVICES.items():
            try:
                loader = metric_service_class(config, api_client=api_client, cluster=cluster)
                loader.check_connection()
                self.echo(f"{service_name} found")
                return loader
            except Exception as e:
                self.warning(f"{service_name} not found")

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
        self.debug(f"Gathering data for {object} and {resource}")

        await self.add_historic_pods(object, period)

        MetricLoaderType = BaseMetricLoader.get_by_resource(resource)
        metric_loader = MetricLoaderType(self.config, self.prometheus)
        return await metric_loader.load_data(object, period, step)

    async def add_historic_pods(self, object: K8sObjectData, period: datetime.timedelta) -> None:
        """
        Finds pods that have been deleted but still have some metrics in Prometheus.

        Args:
            object (K8sObjectData): The Kubernetes object.
            period (datetime.timedelta): The time period for which to gather data.
        """

        days_literal = min(int(period.total_seconds()) // 60 // 24, 32)
        period_literal = f"{days_literal}d"
        pod_owners: list[str]
        pod_owner_kind: str

        if object.kind == "Deployment":
            replicasets = await self.query(
                "kube_replicaset_owner{"
                f'owner_name="{object.name}", '
                f'owner_kind="Deployment", '
                f'namespace="{object.namespace}"'
                "}"
                f"[{period_literal}]"
            )
            pod_owners = [replicaset["metric"]["replicaset"] for replicaset in replicasets]
            pod_owner_kind = "ReplicaSet"
        else:
            pod_owners = [object.name]
            pod_owner_kind = object.kind

        owners_regex = "|".join(pod_owners)
        related_pods = await self.query(
            "kube_pod_owner{"
            f'owner_name=~"{owners_regex}", '
            f'owner_kind="{pod_owner_kind}", '
            f'namespace="{object.namespace}"'
            "}"
            f"[{period_literal}]"
        )

        current_pods = {p.name for p in object.pods}

        object.pods += [
            PodData(name=pod["metric"]["pod"], deleted=True)
            for pod in related_pods
            if pod["metric"]["pod"] not in current_pods
        ]
