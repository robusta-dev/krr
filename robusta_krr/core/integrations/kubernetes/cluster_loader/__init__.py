from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Optional

from kubernetes import client, config  # type: ignore
from kubernetes.client import ApiException  # type: ignore
from kubernetes.client.models import V1Container, V2HorizontalPodAutoscaler  # type: ignore
from functools import cache

from robusta_krr.core.integrations.prometheus.connector import PrometheusConnector
from robusta_krr.core.integrations.prometheus.metrics_service.prometheus_metrics_service import PrometheusMetricsService
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.exceptions import CriticalRunnerException
from robusta_krr.core.models.objects import HPAData, HPAKey, K8sWorkload, KindLiteral, PodData
from robusta_krr.core.models.result import ResourceAllocations


from robusta_krr.core.abstract.workload_loader import BaseWorkloadLoader, IListPodsFallback
from robusta_krr.core.abstract.cluster_loader import BaseClusterLoader
from .loaders import (
    BaseKindLoader,
    CronJobLoader,
    DaemonSetLoader,
    DeploymentConfigLoader,
    DeploymentLoader,
    JobLoader,
    RolloutLoader,
    StatefulSetLoader,
)

logger = logging.getLogger("krr")


class KubeAPIClusterLoader(BaseClusterLoader):
    # NOTE: For KubeAPIClusterLoader we have to first connect to read kubeconfig
    # We do not need to connect to Prometheus from here, as we query all data from Kubernetes API
    # Also here we might have different Prometeus instances for different clusters

    def __init__(self) -> None:
        try:
            settings.load_kubeconfig()
        except Exception as e:
            logger.error(f"Could not load kubernetes configuration: {e.__class__.__name__}\n{e}")
            logger.error("Try to explicitly set --context and/or --kubeconfig flags.")
            logger.error("Alternatively, try a prometheus-only mode with `--mode prometheus`")
            raise CriticalRunnerException("Could not load kubernetes configuration") from e

        self._prometheus_connectors: dict[Optional[str], PrometheusConnector] = {}

    async def list_clusters(self) -> Optional[list[str]]:
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

    @cache
    def get_workload_loader(self, cluster: Optional[str]) -> KubeAPIWorkloadLoader:
        return KubeAPIWorkloadLoader(cluster)

    @cache
    def get_prometheus(self, cluster: Optional[str]) -> PrometheusConnector:
        connector = PrometheusConnector(cluster=cluster)
        if settings.prometheus_url is not None:
            logger.info(f"Connecting to Prometheus using URL: {settings.prometheus_url}")
            connector.connect(settings.prometheus_url)
        else:
            logger.info(f"Trying to discover PromQL service" + (f" for cluster {cluster}" if cluster else ""))
            connector.discover(api_client=settings.get_kube_client(cluster))

        return connector


class KubeAPIWorkloadLoader(BaseWorkloadLoader, IListPodsFallback):
    kind_loaders: list[BaseKindLoader] = [
        DeploymentLoader,
        RolloutLoader,
        DeploymentConfigLoader,
        StatefulSetLoader,
        DaemonSetLoader,
        JobLoader,
        CronJobLoader,
    ]

    def __init__(self, cluster: Optional[str]) -> None:
        self.cluster = cluster

        # This executor will be running requests to Kubernetes API
        self.executor = ThreadPoolExecutor(settings.max_workers)
        self.api_client = settings.get_kube_client(cluster)

        self.autoscaling_v1 = client.AutoscalingV1Api(api_client=self.api_client)
        self.autoscaling_v2 = client.AutoscalingV2Api(api_client=self.api_client)

        self._kind_available: defaultdict[KindLiteral, bool] = defaultdict(lambda: True)
        self._hpa_list: dict[HPAKey, HPAData] = {}
        self._workload_loaders: dict[KindLiteral, BaseKindLoader] = {
            loader.kind: loader(self.api_client, self.executor) for loader in self.kind_loaders
        }

    async def list_workloads(self) -> list[K8sWorkload]:
        """List all scannable objects.

        Returns:
            A list of scannable objects.
        """

        logger.info(f"Listing scannable objects in {self.cluster}")
        logger.debug(f"Namespaces: {settings.namespaces}")
        logger.debug(f"Resources: {settings.resources}")

        self._hpa_list = await self._try_list_hpa()
        workload_object_lists = await asyncio.gather(
            *[
                self._fetch_workload(loader)
                for loader in self._workload_loaders.values()
                if self._should_list_resource(loader.kind)
            ]
        )

        return [
            object
            for workload_objects in workload_object_lists
            for object in workload_objects
            # NOTE: By default we will filter out kube-system namespace
            if not (settings.namespaces == "*" and object.namespace == "kube-system")
        ]

    async def load_pods(self, object: K8sWorkload) -> list[PodData]:
        return await self._workload_loaders[object.kind].list_pods(object)

    def _build_scannable_object(self, item: Any, container: V1Container, kind: Optional[str] = None) -> K8sWorkload:
        name = item.metadata.name
        namespace = item.metadata.namespace
        kind = kind or item.__class__.__name__[2:]

        obj = K8sWorkload(
            cluster=self.cluster,
            namespace=namespace,
            name=name,
            kind=kind,
            container=container.name,
            allocations=ResourceAllocations.from_container(container),
            hpa=self._hpa_list.get(HPAKey(namespace=namespace, kind=kind, name=name)),
        )
        obj._api_resource = item
        return obj

    def _should_list_resource(self, resource: str) -> bool:
        if settings.resources == "*":
            return True
        return resource in settings.resources

    async def _list_namespaced_or_global_objects(
        self,
        kind: KindLiteral,
        all_namespaces_request: Callable[..., Awaitable[Any]],
        namespaced_request: Callable[..., Awaitable[Any]],
    ) -> list[Any]:
        logger.debug(f"Listing {kind}s in {self.cluster}")

        if settings.namespaces == "*":
            requests = [
                all_namespaces_request(
                    label_selector=settings.selector,
                )
            ]
        else:
            requests = [
                namespaced_request(
                    namespace=namespace,
                    label_selector=settings.selector,
                )
                for namespace in settings.namespaces
            ]

        result = [item for request_result in await asyncio.gather(*requests) for item in request_result.items]

        logger.debug(f"Found {len(result)} {kind}" + (f" for cluster {self.cluster}" if self.cluster else ""))
        return result

    async def _fetch_workload(self, loader: BaseKindLoader) -> list[K8sWorkload]:
        kind = loader.kind

        if not self._should_list_resource(kind):
            logger.debug(f"Skipping {kind}s" + (f" for cluster {self.cluster}" if self.cluster else ""))
            return

        if not self._kind_available[kind]:
            return

        result = []
        try:
            for item in await self._list_namespaced_or_global_objects(
                kind, loader.all_namespaces_request_async, loader.namespaced_request_async
            ):
                if not loader.filter(item):
                    continue

                containers = await loader.extract_containers(item)
                if asyncio.iscoroutine(containers):
                    containers = await containers

                result.extend(self._build_scannable_object(item, container, kind) for container in containers)
        except ApiException as e:
            if kind in ("Rollout", "DeploymentConfig") and e.status in [400, 401, 403, 404]:
                if self._kind_available[kind]:
                    logger.debug(f"{kind} API not available in {self.cluster}")
                self._kind_available[kind] = False
            else:
                logger.exception(f"Error {e.status} listing {kind} in cluster {self.cluster}: {e.reason}")
                logger.error("Will skip this object type and continue.")

        return result

    async def __list_hpa_v1(self) -> dict[HPAKey, HPAData]:
        loop = asyncio.get_running_loop()
        res = await self._list_namespaced_or_global_objects(
            kind="HPA-v1",
            all_namespaces_request=lambda **kwargs: loop.run_in_executor(
                self.executor,
                lambda: self.autoscaling_v1.list_horizontal_pod_autoscaler_for_all_namespaces(**kwargs),
            ),
            namespaced_request=lambda **kwargs: loop.run_in_executor(
                self.executor,
                lambda: self.autoscaling_v1.list_namespaced_horizontal_pod_autoscaler(**kwargs),
            ),
        )

        return {
            HPAKey(
                namespace=hpa.metadata.namespace,
                kind=hpa.spec.scale_target_ref.kind,
                name=hpa.spec.scale_target_ref.name,
            ): HPAData(
                min_replicas=hpa.spec.min_replicas,
                max_replicas=hpa.spec.max_replicas,
                target_cpu_utilization_percentage=hpa.spec.target_cpu_utilization_percentage,
                target_memory_utilization_percentage=None,
            )
            async for hpa in res
        }

    async def __list_hpa_v2(self) -> dict[HPAKey, HPAData]:
        loop = asyncio.get_running_loop()

        res = await self._list_namespaced_or_global_objects(
            kind="HPA-v2",
            all_namespaces_request=lambda **kwargs: loop.run_in_executor(
                self.executor,
                lambda: self.autoscaling_v2.list_horizontal_pod_autoscaler_for_all_namespaces(**kwargs),
            ),
            namespaced_request=lambda **kwargs: loop.run_in_executor(
                self.executor,
                lambda: self.autoscaling_v2.list_namespaced_horizontal_pod_autoscaler(**kwargs),
            ),
        )

        def __get_metric(hpa: V2HorizontalPodAutoscaler, metric_name: str) -> Optional[float]:
            return next(
                (
                    metric.resource.target.average_utilization
                    for metric in hpa.spec.metrics
                    if metric.type == "Resource" and metric.resource.name == metric_name
                ),
                None,
            )

        return {
            HPAKey(
                namespace=hpa.metadata.namespace,
                kind=hpa.spec.scale_target_ref.kind,
                name=hpa.spec.scale_target_ref.name,
            ): HPAData(
                min_replicas=hpa.spec.min_replicas,
                max_replicas=hpa.spec.max_replicas,
                target_cpu_utilization_percentage=__get_metric(hpa, "cpu"),
                target_memory_utilization_percentage=__get_metric(hpa, "memory"),
            )
            for hpa in res
        }

    # TODO: What should we do in case of other metrics bound to the HPA?
    async def __list_hpa(self) -> dict[HPAKey, HPAData]:
        """List all HPA objects in the cluster.

        Returns:
            dict[tuple[str, str], HPAData]: A dictionary of HPA objects, indexed by scaleTargetRef (kind, name).
        """

        try:
            # Try to use V2 API first
            return await self.__list_hpa_v2()
        except ApiException as e:
            if e.status != 404:
                # If the error is other than not found, then re-raise it.
                raise

            # If V2 API does not exist, fall back to V1
            return await self.__list_hpa_v1()

    async def _try_list_hpa(self) -> dict[HPAKey, HPAData]:
        try:
            return await self.__list_hpa()
        except Exception as e:
            logger.exception(f"Error trying to list hpa in cluster {self.cluster}: {e}")
            logger.error(
                "Will assume that there are no HPA. "
                "Be careful as this may lead to inaccurate results if object actually has HPA."
            )
            return {}


__all__ = ["KubeAPIWorkloadLoader", "KubeAPIClusterLoader"]
