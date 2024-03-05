import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncGenerator, AsyncIterator, Callable, Optional, Union, Any

import aiostream
from kubernetes import client, config  # type: ignore
from kubernetes.client import ApiException
from kubernetes.client.models import (
    V1Container,
    V1DaemonSet,
    V1Deployment,
    V1HorizontalPodAutoscalerList,
    V1Job,
    V1LabelSelector,
    V1Pod,
    V1PodList,
    V1StatefulSet,
    V2HorizontalPodAutoscaler,
    V2HorizontalPodAutoscalerList,
)

from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import HPAData, K8sObjectData, KindLiteral, PodData
from robusta_krr.core.models.result import ResourceAllocations

from . import config_patch as _
from .rollout import RolloutAppsV1Api

logger = logging.getLogger("krr")

AnyKubernetesAPIObject = Union[V1Deployment, V1DaemonSet, V1StatefulSet, V1Pod, V1Job]
HPAKey = tuple[str, str, str]


class ClusterLoader:
    def __init__(self, cluster: Optional[str]=None):
        self.cluster = cluster
        # This executor will be running requests to Kubernetes API
        self.executor = ThreadPoolExecutor(settings.max_workers)
        self.api_client = settings.get_kube_client(cluster)
        self.apps = client.AppsV1Api(api_client=self.api_client)
        self.rollout = RolloutAppsV1Api(api_client=self.api_client)
        self.batch = client.BatchV1Api(api_client=self.api_client)
        self.core = client.CoreV1Api(api_client=self.api_client)
        self.autoscaling_v1 = client.AutoscalingV1Api(api_client=self.api_client)
        self.autoscaling_v2 = client.AutoscalingV2Api(api_client=self.api_client)

        self.__rollouts_available = True

    async def list_scannable_objects(self) -> AsyncGenerator[K8sObjectData, None]:
        """List all scannable objects.

        Returns:
            A list of scannable objects.
        """

        logger.info(f"Listing scannable objects in {self.cluster}")
        logger.debug(f"Namespaces: {settings.namespaces}")
        logger.debug(f"Resources: {settings.resources}")

        self.__hpa_list = await self._try_list_hpa()

        # https://stackoverflow.com/questions/55299564/join-multiple-async-generators-in-python
        # This will merge all the streams from all the cluster loaders into a single stream
        objects_combined = aiostream.stream.merge(
            self._list_deployments(),
            self._list_rollouts(),
            self._list_all_statefulsets(),
            self._list_all_daemon_set(),
            self._list_all_jobs(),
        )

        async with objects_combined.stream() as streamer:
            async for object in streamer:
                # NOTE: By default we will filter out kube-system namespace
                if settings.namespaces == "*" and object.namespace == "kube-system":
                    continue
                yield object

    async def list_pods(self, object: K8sObjectData) -> list[PodData]:
        selector = self._build_selector_query(object._api_resource.spec.selector)
        if selector is None:
            return []

        loop = asyncio.get_running_loop()
        ret: V1PodList = await loop.run_in_executor(
            self.executor,
            lambda: self.core.list_namespaced_pod(
                namespace=object._api_resource.metadata.namespace, label_selector=selector
            ),
        )
        return [PodData(name=pod.metadata.name, deleted=False) for pod in ret.items]

    @staticmethod
    def _get_match_expression_filter(expression) -> str:
        if expression.operator.lower() == "exists":
            return expression.key
        elif expression.operator.lower() == "doesnotexist":
            return f"!{expression.key}"

        values = ",".join(expression.values)
        return f"{expression.key} {expression.operator} ({values})"

    @staticmethod
    def _build_selector_query(selector: V1LabelSelector) -> Union[str, None]:
        label_filters = [f"{label[0]}={label[1]}" for label in selector.match_labels.items()]

        if selector.match_expressions is not None:
            label_filters.extend(
                [ClusterLoader._get_match_expression_filter(expression) for expression in selector.match_expressions]
            )

        return ",".join(label_filters)

    def __build_scannable_object(
        self, item: AnyKubernetesAPIObject, container: V1Container, kind: Optional[str] = None
    ) -> K8sObjectData:
        name = item.metadata.name
        namespace = item.metadata.namespace
        kind = kind or item.__class__.__name__[2:]

        obj = K8sObjectData(
            cluster=self.cluster,
            namespace=namespace,
            name=name,
            kind=kind,
            container=container.name,
            allocations=ResourceAllocations.from_container(container),
            hpa=self.__hpa_list.get((namespace, kind, name)),
        )
        obj._api_resource = item
        return obj

    def _should_list_resource(self, resource: str):
        if settings.resources == "*":
            return True
        return resource.capitalize() in settings.resources

    async def _list_namespaced_or_global_objects(
        self, kind: KindLiteral, all_namespaces_request: Callable, namespaced_request: Callable
    ) -> AsyncIterator[Any]:
        logger.debug(f"Listing {kind}s in {self.cluster}")
        loop = asyncio.get_running_loop()

        if settings.namespaces == "*":
            ret_multi = await loop.run_in_executor(
                self.executor,
                lambda: all_namespaces_request(
                    watch=False,
                    label_selector=settings.selector,
                ),
            )
            logger.debug(f"Found {len(ret_multi.items)} {kind} in {self.cluster}")
            for item in ret_multi.items:
                yield item
        else:
            tasks = [
                loop.run_in_executor(
                    self.executor,
                    lambda ns=namespace: namespaced_request(
                        namespace=ns,
                        watch=False,
                        label_selector=settings.selector,
                    ),
                )
                for namespace in settings.namespaces
            ]

            total_items = 0
            for task in asyncio.as_completed(tasks):
                ret_single = await task
                total_items += len(ret_single.items)
                for item in ret_single.items:
                    yield item

            logger.debug(f"Found {total_items} {kind} in {self.cluster}")

    async def _list_scannable_objects(
        self, kind: KindLiteral, all_namespaces_request: Callable, namespaced_request: Callable
    ) -> AsyncIterator[K8sObjectData]:
        if not self._should_list_resource(kind):
            logger.debug(f"Skipping {kind}s in {self.cluster}")
            return

        if kind == "Rollout" and not self.__rollouts_available:
            return

        try:
            async for item in self._list_namespaced_or_global_objects(kind, all_namespaces_request, namespaced_request):
                for container in item.spec.template.spec.containers:
                    yield self.__build_scannable_object(item, container, kind)
        except ApiException as e:
            if kind == "Rollout" and e.status in [400, 401, 403, 404]:
                if self.__rollouts_available:
                    logger.debug(f"Rollout API not available in {self.cluster}")
                self.__rollouts_available = False
            else:
                logger.exception(f"Error {e.status} listing {kind} in cluster {self.cluster}: {e.reason}")
                logger.error("Will skip this object type and continue.")

    def _list_deployments(self) -> AsyncIterator[K8sObjectData]:
        return self._list_scannable_objects(
            kind="Deployment",
            all_namespaces_request=self.apps.list_deployment_for_all_namespaces,
            namespaced_request=self.apps.list_namespaced_deployment,
        )

    def _list_rollouts(self) -> AsyncIterator[K8sObjectData]:
        return self._list_scannable_objects(
            kind="Rollout",
            all_namespaces_request=self.rollout.list_rollout_for_all_namespaces,
            namespaced_request=self.rollout.list_namespaced_rollout,
        )

    def _list_all_statefulsets(self) -> AsyncIterator[K8sObjectData]:
        return self._list_scannable_objects(
            kind="StatefulSet",
            all_namespaces_request=self.apps.list_stateful_set_for_all_namespaces,
            namespaced_request=self.apps.list_namespaced_stateful_set,
        )

    def _list_all_daemon_set(self) -> AsyncIterator[K8sObjectData]:
        return self._list_scannable_objects(
            kind="DaemonSet",
            all_namespaces_request=self.apps.list_daemon_set_for_all_namespaces,
            namespaced_request=self.apps.list_namespaced_daemon_set,
        )

    def _list_all_jobs(self) -> AsyncIterator[K8sObjectData]:
        return self._list_scannable_objects(
            kind="Job",
            all_namespaces_request=self.batch.list_job_for_all_namespaces,
            namespaced_request=self.batch.list_namespaced_job,
        )

    async def __list_hpa_v1(self) -> dict[HPAKey, HPAData]:
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(
            self.executor,
            lambda: self._list_namespaced_or_global_objects(
                kind="HPA-v1",
                all_namespaces_request=self.autoscaling_v1.list_horizontal_pod_autoscaler_for_all_namespaces,
                namespaced_request=self.autoscaling_v1.list_namespaced_horizontal_pod_autoscaler,
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
        res = await loop.run_in_executor(
            self.executor,
            lambda: self._list_namespaced_or_global_objects(
                kind="HPA-v2",
                all_namespaces_request=self.autoscaling_v2.list_horizontal_pod_autoscaler_for_all_namespaces,
                namespaced_request=self.autoscaling_v2.list_namespaced_horizontal_pod_autoscaler,
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
            async for hpa in res
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


class KubernetesLoader:
    def __init__(self) -> None:
        self._cluster_loaders: dict[Optional[str], ClusterLoader] = {}

    async def list_clusters(self) -> Optional[list[str]]:
        """List all clusters.

        Returns:
            A list of clusters.
        """

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

    def _try_create_cluster_loader(self, cluster: Optional[str]) -> Optional[ClusterLoader]:
        try:
            return ClusterLoader(cluster=cluster)
        except Exception as e:
            logger.error(f"Could not load cluster {cluster} and will skip it: {e}")
            return None

    async def list_scannable_objects(self, clusters: Optional[list[str]]) -> AsyncIterator[K8sObjectData]:
        """List all scannable objects.

        Yields:
            Each scannable object as it is loaded.
        """
        if clusters is None:
            _cluster_loaders = [self._try_create_cluster_loader(None)]
        else:
            _cluster_loaders = [self._try_create_cluster_loader(cluster) for cluster in clusters]

        self.cluster_loaders = {cl.cluster: cl for cl in _cluster_loaders if cl is not None}
        if self.cluster_loaders == {}:
            logger.error("Could not load any cluster.")
            return

        # https://stackoverflow.com/questions/55299564/join-multiple-async-generators-in-python
        # This will merge all the streams from all the cluster loaders into a single stream
        objects_combined = aiostream.stream.merge(
            *[cluster_loader.list_scannable_objects() for cluster_loader in self.cluster_loaders.values()]
        )

        async with objects_combined.stream() as streamer:
            async for object in streamer:
                yield object

    async def load_pods(self, object: K8sObjectData) -> list[PodData]:
        try:
            cluster_loader = self.cluster_loaders[object.cluster]
        except KeyError:
            raise RuntimeError(f"Cluster loader for cluster {object.cluster} not found") from None

        return await cluster_loader.list_pods(object)
