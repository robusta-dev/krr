import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Iterable, List, Optional

from kubernetes.client import ApiClient
from prometheus_api_client import PrometheusApiClientException
from prometrix import PrometheusNotFound, get_custom_prometheus_connect

from robusta_krr.core.abstract.strategies import PodsTimeData
from robusta_krr.core.integrations import openshift
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import K8sObjectData, PodData
from robusta_krr.utils.batched import batched
from robusta_krr.utils.service_discovery import MetricsServiceDiscovery

from ..metrics import PrometheusMetric
from ..prometheus_utils import ClusterNotSpecifiedException, generate_prometheus_config
from .base_metric_service import MetricsService

logger = logging.getLogger("krr")


class PrometheusDiscovery(MetricsServiceDiscovery):
    def find_metrics_url(self, *, api_client: Optional[ApiClient] = None) -> Optional[str]:
        """
        Finds the Prometheus URL using selectors.
        Args:
            api_client (Optional[ApiClient]): A Kubernetes API client. Defaults to None.
        Returns:
            Optional[str]: The discovered Prometheus URL, or None if not found.
        """

        return super().find_url(
            selectors=[
                "app=kube-prometheus-stack-prometheus",
                "app=prometheus,component=server",
                "app=prometheus-server",
                "app=prometheus-operator-prometheus",
                "app=prometheus-msteams",
                "app=rancher-monitoring-prometheus",
                "app=prometheus-prometheus",
            ]
        )


class PrometheusMetricsService(MetricsService):
    """
    A class for fetching metrics from Prometheus.
    """

    service_discovery: type[MetricsServiceDiscovery] = PrometheusDiscovery

    def __init__(
        self,
        *,
        cluster: Optional[str] = None,
        api_client: Optional[ApiClient] = None,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        super().__init__(api_client=api_client, cluster=cluster, executor=executor)

        logger.info(f"Connecting to {self.name} for {self.cluster} cluster")

        self.auth_header = settings.prometheus_auth_header
        self.ssl_enabled = settings.prometheus_ssl_enabled

        if settings.openshift:
            logging.info("Openshift flag is set, trying to load token from service account.")
            openshift_token = openshift.load_token()

            if openshift_token:
                logging.info("Openshift token is loaded successfully.")
                self.auth_header = self.auth_header or f"Bearer {openshift_token}"
            else:
                logging.warning("Openshift token is not found, trying to connect without it.")

        self.prometheus_discovery = self.service_discovery(api_client=self.api_client)

        self.url = settings.prometheus_url
        self.url = self.url or self.prometheus_discovery.find_metrics_url()

        if not self.url:
            raise PrometheusNotFound(
                f"{self.name} instance could not be found while scanning in {self.cluster} cluster.\n"
                "\tTry using port-forwarding and/or setting the url manually (using the -p flag.)."
            )

        logger.info(f"Using {self.name} at {self.url} for cluster {cluster or 'default'}")

        headers = settings.prometheus_other_headers

        if self.auth_header:
            headers |= {"Authorization": self.auth_header}
        elif not settings.inside_cluster and self.api_client is not None:
            self.api_client.update_params_for_auth(headers, {}, ["BearerToken"])
        self.prom_config = generate_prometheus_config(url=self.url, headers=headers, metrics_service=self)
        self.prometheus = get_custom_prometheus_connect(self.prom_config)

    def check_connection(self):
        """
        Checks the connection to Prometheus.
        Raises:
            PrometheusNotFound: If the connection to Prometheus cannot be established.
        """
        self.prometheus.check_prometheus_connection()

    async def query(self, query: str) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: self.prometheus.safe_custom_query(query=query)["result"],
        )

    async def query_range(self, query: str, start: datetime, end: datetime, step: timedelta) -> dict:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: self.prometheus.safe_custom_query_range(
                query=query, start_time=start, end_time=end, step=f"{step.seconds}s"
            )["result"],
        )

    def validate_cluster_name(self):
        if not settings.prometheus_cluster_label and not settings.prometheus_label:
            return

        cluster_label = settings.prometheus_cluster_label
        cluster_names = self.get_cluster_names()

        if cluster_names is None or len(cluster_names) <= 1:
            # there is only one cluster of metrics in this prometheus
            return

        if not cluster_label:
            raise ClusterNotSpecifiedException(
                f"No label specified, Rerun krr with the flag `-l <cluster>` where <cluster> is one of {cluster_names}"
            )
        if cluster_label not in cluster_names:
            raise ClusterNotSpecifiedException(
                f"Label {cluster_label} does not exist, Rerun krr with the flag `-l <cluster>` where <cluster> is one of {cluster_names}"
            )

    def get_cluster_names(self) -> Optional[List[str]]:
        try:
            return self.prometheus.get_label_values(label_name=settings.prometheus_label)
        except PrometheusApiClientException:
            logger.error("Labels api not present on prometheus client")
            return []

    async def get_history_range(self, history_duration: timedelta) -> tuple[datetime, datetime]:
        """
        Get the history range from Prometheus, based on container_memory_working_set_bytes.
        Returns:
            float: The first history point.
        """

        now = datetime.now()
        result = await self.query_range(
            "max(prometheus_tsdb_head_series)",
            start=now - history_duration,
            end=now,
            step=timedelta(hours=1),
        )
        try:
            values = result[0]["values"]
            start, end = values[0][0], values[-1][0]
            return datetime.fromtimestamp(start), datetime.fromtimestamp(end)
        except (KeyError, IndexError) as e:
            logger.debug(f"Returned from get_history_range: {result}")
            raise ValueError("Error while getting history range") from e

    async def gather_data(
        self,
        object: K8sObjectData,
        LoaderClass: type[PrometheusMetric],
        period: timedelta,
        step: timedelta = timedelta(minutes=30),
    ) -> PodsTimeData:
        """
        ResourceHistoryData: The gathered resource history data.
        """
        logger.debug(f"Gathering {LoaderClass.__name__} metric for {object}")

        metric_loader = LoaderClass(self.prometheus, self.name, self.executor)
        data = await metric_loader.load_data(object, period, step)

        if len(data) == 0:
            if "CPU" in LoaderClass.__name__:
                object.add_warning("NoPrometheusCPUMetrics")
            elif "Memory" in LoaderClass.__name__:
                object.add_warning("NoPrometheusMemoryMetrics")

            logger.warning(
                f"{metric_loader.service_name} returned no {metric_loader.__class__.__name__} metrics for {object}"
            )

        return data

    async def load_pods(self, object: K8sObjectData, period: timedelta) -> list[PodData]:
        """
        List pods related to the object and add them to the object's pods list.
        Args:
            object (K8sObjectData): The Kubernetes object.
            period (timedelta): The time period for which to gather data.
        """

        logger.debug(f"Adding historic pods for {object}")

        days_literal = min(int(period.total_seconds()) // 60 // 24, 32)
        period_literal = f"{days_literal}d"
        pod_owners: Iterable[str]
        pod_owner_kind: str
        cluster_label = self.get_prometheus_cluster_label()
        if object.kind in ["Deployment", "Rollout"]:
            replicasets = await self.query(
                f"""
                    kube_replicaset_owner{{
                        owner_name="{object.name}",
                        owner_kind="{object.kind}",
                        namespace="{object.namespace}"
                        {cluster_label}
                    }}[{period_literal}]
                """
            )
            pod_owners = {replicaset["metric"]["replicaset"] for replicaset in replicasets}
            pod_owner_kind = "ReplicaSet"

            del replicasets

        elif object.kind == "DeploymentConfig":
            replication_controllers = await self.query(
                f"""
                    kube_replicationcontroller_owner{{
                        owner_name="{object.name}",
                        owner_kind="{object.kind}",
                        namespace="{object.namespace}"
                        {cluster_label}
                    }}[{period_literal}]
                """
            )
            pod_owners = {repl_controller["metric"]["replicationcontroller"] for repl_controller in replication_controllers}
            pod_owner_kind = "ReplicationController"

            del replication_controllers

        elif object.kind == "CronJob":
            jobs = await self.query(
                f"""
                    kube_job_owner{{
                        owner_name="{object.name}",
                        owner_kind="{object.kind}",
                        namespace="{object.namespace}"
                        {cluster_label}
                    }}[{period_literal}]
                """
            )
            pod_owners = {job["metric"]["job_name"] for job in jobs}
            pod_owner_kind = "Job"

            del jobs
        else:
            pod_owners = [object.name]
            pod_owner_kind = object.kind

        owners_regex = "|".join(pod_owners)
        related_pods_result = await self.query(
            f"""
                last_over_time(
                    kube_pod_owner{{
                        owner_name=~"{owners_regex}",
                        owner_kind="{pod_owner_kind}",
                        namespace="{object.namespace}"
                        {cluster_label}
                    }}[{period_literal}]
                )
            """
        )

        if related_pods_result == []:
            return []

        related_pods = [pod["metric"]["pod"] for pod in related_pods_result]
        current_pods_set = set()
        del related_pods_result

        for pod_group in batched(related_pods, 100):
            group_regex = "|".join(pod_group)
            pods_status_result = await self.query(
                f"""
                    kube_pod_status_phase{{
                        phase="Running",
                        pod=~"{group_regex}",
                        namespace="{object.namespace}"
                        {cluster_label}
                    }} == 1
                """
            )
            current_pods_set |= {pod["metric"]["pod"] for pod in pods_status_result}
            del pods_status_result

        return list({PodData(name=pod, deleted=pod not in current_pods_set) for pod in related_pods})
