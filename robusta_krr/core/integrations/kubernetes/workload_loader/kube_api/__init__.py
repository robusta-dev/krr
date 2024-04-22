import asyncio
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Optional

from kubernetes import client  # type: ignore
from kubernetes.client import ApiException  # type: ignore
from kubernetes.client.models import V1Container, V2HorizontalPodAutoscaler  # type: ignore

from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import HPAData, K8sWorkload, KindLiteral, PodData
from robusta_krr.core.models.result import ResourceAllocations

from ..base import BaseWorkloadLoader
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

HPAKey = tuple[str, str, str]


class KubeAPIWorkloadLoader(BaseWorkloadLoader):
    workload_loaders: list[BaseKindLoader] = [
        DeploymentLoader,
        RolloutLoader,
        DeploymentConfigLoader,
        StatefulSetLoader,
        DaemonSetLoader,
        JobLoader,
        CronJobLoader,
    ]

    def __init__(self, cluster: Optional[str] = None) -> None:
        self.cluster = cluster

        # This executor will be running requests to Kubernetes API
        self.executor = ThreadPoolExecutor(settings.max_workers)
        self.api_client = settings.get_kube_client(cluster)

        self.autoscaling_v1 = client.AutoscalingV1Api(api_client=self.api_client)
        self.autoscaling_v2 = client.AutoscalingV2Api(api_client=self.api_client)

        self._kind_available: defaultdict[KindLiteral, bool] = defaultdict(lambda: True)
        self._hpa_list: dict[HPAKey, HPAData] = {}
        self._workload_loaders: dict[KindLiteral, BaseKindLoader] = {
            loader.kind: loader(self.api_client, self.executor) for loader in self.workload_loaders
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

    async def list_pods(self, object: K8sWorkload) -> list[PodData]:
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
            hpa=self._hpa_list.get((namespace, kind, name)),
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

        logger.debug(f"Found {len(result)} {kind} in {self.cluster}")
        return result

    async def _fetch_workload(self, loader: BaseKindLoader) -> list[K8sWorkload]:
        kind = loader.kind

        if not self._should_list_resource(kind):
            logger.debug(f"Skipping {kind}s in {self.cluster}")
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
                self.autoscaling_v1.list_horizontal_pod_autoscaler_for_all_namespaces(**kwargs),
            ),
            namespaced_request=lambda **kwargs: loop.run_in_executor(
                self.autoscaling_v1.list_namespaced_horizontal_pod_autoscaler(**kwargs),
            ),
        )

        return {
            (
                hpa.metadata.namespace,
                hpa.spec.scale_target_ref.kind,
                hpa.spec.scale_target_ref.name,
            ): HPAData(
                min_replicas=hpa.spec.min_replicas,
                max_replicas=hpa.spec.max_replicas,
                current_replicas=hpa.status.current_replicas,
                desired_replicas=hpa.status.desired_replicas,
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
                self.executor, self.autoscaling_v2.list_horizontal_pod_autoscaler_for_all_namespaces(**kwargs)
            ),
            namespaced_request=lambda **kwargs: loop.run_in_executor(
                self.autoscaling_v2.list_namespaced_horizontal_pod_autoscaler(**kwargs),
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
            (
                hpa.metadata.namespace,
                hpa.spec.scale_target_ref.kind,
                hpa.spec.scale_target_ref.name,
            ): HPAData(
                min_replicas=hpa.spec.min_replicas,
                max_replicas=hpa.spec.max_replicas,
                current_replicas=hpa.status.current_replicas,
                desired_replicas=hpa.status.desired_replicas,
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


__all__ = ["KubeAPIWorkloadLoader"]
