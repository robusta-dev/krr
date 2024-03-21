import asyncio
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, AsyncIterable, Awaitable, Callable, Iterable, Optional, Union

from kubernetes import client, config  # type: ignore
from kubernetes.client import ApiException
from kubernetes.client.models import (
    V1Container,
    V1DaemonSet,
    V1Deployment,
    V1HorizontalPodAutoscalerList,
    V1Job,
    V1Pod,
    V1PodList,
    V1StatefulSet,
    V2HorizontalPodAutoscaler,
    V2HorizontalPodAutoscalerList,
)

from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import HPAData, K8sObjectData, KindLiteral, PodData
from robusta_krr.core.models.result import ResourceAllocations
from robusta_krr.utils.async_gen_merge import async_gen_merge
from robusta_krr.utils.object_like_dict import ObjectLikeDict

from . import config_patch as _

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
        self.custom_objects = client.CustomObjectsApi(api_client=self.api_client)
        self.batch = client.BatchV1Api(api_client=self.api_client)
        self.core = client.CoreV1Api(api_client=self.api_client)
        self.autoscaling_v1 = client.AutoscalingV1Api(api_client=self.api_client)
        self.autoscaling_v2 = client.AutoscalingV2Api(api_client=self.api_client)

        self.__kind_available: defaultdict[KindLiteral, bool] = defaultdict(lambda: True)

        self.__jobs_for_cronjobs: dict[str, list[V1Job]] = {}
        self.__jobs_loading_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

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
        async for object in async_gen_merge(
            self._list_deployments(),
            self._list_rollouts(),
            self._list_deploymentconfig(),
            self._list_all_statefulsets(),
            self._list_all_daemon_set(),
            self._list_all_jobs(),
            self._list_all_cronjobs(),
        ):
            # NOTE: By default we will filter out kube-system namespace
            if settings.namespaces == "*" and object.namespace == "kube-system":
                continue
            yield object

    async def _list_jobs_for_cronjobs(self, namespace: str) -> list[V1Job]:
        if namespace not in self.__jobs_for_cronjobs:
            loop = asyncio.get_running_loop()

            async with self.__jobs_loading_locks[namespace]:
                logging.debug(f"Loading jobs for cronjobs in {namespace}")
                ret = await loop.run_in_executor(
                    self.executor,
                    lambda: self.batch.list_namespaced_job(namespace=namespace),
                )
                self.__jobs_for_cronjobs[namespace] = ret.items

        return self.__jobs_for_cronjobs[namespace]

    async def list_pods(self, object: K8sObjectData) -> list[PodData]:
        loop = asyncio.get_running_loop()

        if object.kind == "CronJob":
            namespace_jobs = await self._list_jobs_for_cronjobs(object.namespace)
            ownered_jobs_uids = [
                job.metadata.uid
                for job in namespace_jobs
                if any(
                    owner.kind == "CronJob" and owner.uid == object._api_resource.metadata.uid
                    for owner in job.metadata.owner_references or []
                )
            ]
            selector = f"batch.kubernetes.io/controller-uid in ({','.join(ownered_jobs_uids)})"

        else:
            if object.selector is None:
                return []

            selector = self._build_selector_query(object.selector)
            if selector is None:
                return []

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
    def _build_selector_query(selector: Any) -> Union[str, None]:
        label_filters = []

        if selector.match_labels is not None:
            label_filters += [f"{label[0]}={label[1]}" for label in selector.match_labels.items()]

        if selector.match_expressions is not None:
            label_filters += [
                ClusterLoader._get_match_expression_filter(expression) for expression in selector.match_expressions
            ]

        if label_filters == []:
            # NOTE: This might mean that we have DeploymentConfig,
            # which uses ReplicationController and it has a dict like matchLabels
            if len(selector) != 0:
                label_filters += [f"{label[0]}={label[1]}" for label in selector.items()]
            else:
                return None

        return ",".join(label_filters)

    def __build_obj(
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

    def _should_list_resource(self, resource: str) -> bool:
        if settings.resources == "*":
            return True
        return resource in settings.resources

    async def _list_workflows(
        self,
        kind: KindLiteral,
        all_namespaces_request: Callable,
        namespaced_request: Callable,
        extract_containers: Callable[[Any], Union[Iterable[V1Container], Awaitable[Iterable[V1Container]]]],
        filter_workflows: Optional[Callable[[Any], bool]] = None,
    ) -> AsyncIterable[K8sObjectData]:
        if not self._should_list_resource(kind):
            logger.debug(f"Skipping {kind}s in {self.cluster}")
            return

        if not self.__kind_available[kind]:
            return

        logger.debug(f"Listing {kind}s in {self.cluster}")
        loop = asyncio.get_running_loop()

        try:
            if settings.namespaces == "*":
                tasks = [
                    loop.run_in_executor(
                        self.executor,
                        lambda: all_namespaces_request(
                            watch=False,
                            label_selector=settings.selector,
                        ),
                    )
                ]
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
                    if filter_workflows is not None and not filter_workflows(item):
                        continue

                    containers = extract_containers(item)
                    if asyncio.iscoroutine(containers):
                        containers = await containers

                    for container in containers:
                        yield self.__build_obj(item, container, kind)

            logger.debug(f"Found {total_items} {kind} in {self.cluster}")
        except ApiException as e:
            if kind in ("Rollout", "DeploymentConfig") and e.status in [400, 401, 403, 404]:
                if self.__kind_available[kind]:
                    logger.debug(f"{kind} API not available in {self.cluster}")
                self.__kind_available[kind] = False
            else:
                logger.exception(f"Error {e.status} listing {kind} in cluster {self.cluster}: {e.reason}")
                logger.error("Will skip this object type and continue.")

    def _list_deployments(self) -> AsyncIterable[K8sObjectData]:
        return self._list_workflows(
            kind="Deployment",
            all_namespaces_request=self.apps.list_deployment_for_all_namespaces,
            namespaced_request=self.apps.list_namespaced_deployment,
            extract_containers=lambda item: item.spec.template.spec.containers,
        )

    def _list_rollouts(self) -> AsyncIterable[K8sObjectData]:
        async def _extract_containers(item: Any) -> list[V1Container]:
            if item.spec.template is not None:
                return item.spec.template.spec.containers

            loop = asyncio.get_running_loop()

            logging.debug(
                f"Rollout has workloadRef, fetching template for {item.metadata.name} in {item.metadata.namespace}"
            )

            # Template can be None and object might have workloadRef
            workloadRef = item.spec.workloadRef
            if workloadRef is not None:
                ret = await loop.run_in_executor(
                    self.executor,
                    lambda: self.apps.read_namespaced_deployment(
                        namespace=item.metadata.namespace, name=workloadRef.name
                    ),
                )
                return ret.spec.template.spec.containers

            return []

        # NOTE: Using custom objects API returns dicts, but all other APIs return objects
        # We need to handle this difference using a small wrapper
        return self._list_workflows(
            kind="Rollout",
            all_namespaces_request=lambda **kwargs: ObjectLikeDict(
                self.custom_objects.list_cluster_custom_object(
                    group="argoproj.io",
                    version="v1alpha1",
                    plural="rollouts",
                    **kwargs,
                )
            ),
            namespaced_request=lambda **kwargs: ObjectLikeDict(
                self.custom_objects.list_namespaced_custom_object(
                    group="argoproj.io",
                    version="v1alpha1",
                    plural="rollouts",
                    **kwargs,
                )
            ),
            extract_containers=_extract_containers,
        )

    def _list_deploymentconfig(self) -> AsyncIterable[K8sObjectData]:
        # NOTE: Using custom objects API returns dicts, but all other APIs return objects
        # We need to handle this difference using a small wrapper
        return self._list_workflows(
            kind="DeploymentConfig",
            all_namespaces_request=lambda **kwargs: ObjectLikeDict(
                self.custom_objects.list_cluster_custom_object(
                    group="apps.openshift.io",
                    version="v1",
                    plural="deploymentconfigs",
                    **kwargs,
                )
            ),
            namespaced_request=lambda **kwargs: ObjectLikeDict(
                self.custom_objects.list_namespaced_custom_object(
                    group="apps.openshift.io",
                    version="v1",
                    plural="deploymentconfigs",
                    **kwargs,
                )
            ),
            extract_containers=lambda item: item.spec.template.spec.containers,
        )

    def _list_all_statefulsets(self) -> AsyncIterable[K8sObjectData]:
        return self._list_workflows(
            kind="StatefulSet",
            all_namespaces_request=self.apps.list_stateful_set_for_all_namespaces,
            namespaced_request=self.apps.list_namespaced_stateful_set,
            extract_containers=lambda item: item.spec.template.spec.containers,
        )

    def _list_all_daemon_set(self) -> AsyncIterable[K8sObjectData]:
        return self._list_workflows(
            kind="DaemonSet",
            all_namespaces_request=self.apps.list_daemon_set_for_all_namespaces,
            namespaced_request=self.apps.list_namespaced_daemon_set,
            extract_containers=lambda item: item.spec.template.spec.containers,
        )

    def _list_all_jobs(self) -> AsyncIterable[K8sObjectData]:
        return self._list_workflows(
            kind="Job",
            all_namespaces_request=self.batch.list_job_for_all_namespaces,
            namespaced_request=self.batch.list_namespaced_job,
            extract_containers=lambda item: item.spec.template.spec.containers,
            # NOTE: If the job has ownerReference and it is a CronJob, then we should skip it
            filter_workflows=lambda item: not any(
                owner.kind == "CronJob" for owner in item.metadata.owner_references or []
            ),
        )

    def _list_all_cronjobs(self) -> AsyncIterable[K8sObjectData]:
        return self._list_workflows(
            kind="CronJob",
            all_namespaces_request=self.batch.list_cron_job_for_all_namespaces,
            namespaced_request=self.batch.list_namespaced_cron_job,
            extract_containers=lambda item: item.spec.job_template.spec.template.spec.containers,
        )

    async def __list_hpa_v1(self) -> dict[HPAKey, HPAData]:
        loop = asyncio.get_running_loop()

        res: V1HorizontalPodAutoscalerList = await loop.run_in_executor(
            self.executor, lambda: self.autoscaling_v1.list_horizontal_pod_autoscaler_for_all_namespaces(watch=False)
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
            for hpa in res.items
        }

    async def __list_hpa_v2(self) -> dict[HPAKey, HPAData]:
        loop = asyncio.get_running_loop()

        res: V2HorizontalPodAutoscalerList = await loop.run_in_executor(
            self.executor,
            lambda: self.autoscaling_v2.list_horizontal_pod_autoscaler_for_all_namespaces(watch=False),
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
            for hpa in res.items
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

    async def list_scannable_objects(self, clusters: Optional[list[str]]) -> AsyncIterable[K8sObjectData]:
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
        async for object in async_gen_merge(
            *[cluster_loader.list_scannable_objects() for cluster_loader in self.cluster_loaders.values()]
        ):
            yield object

    async def load_pods(self, object: K8sObjectData) -> list[PodData]:
        try:
            cluster_loader = self.cluster_loaders[object.cluster]
        except KeyError:
            raise RuntimeError(f"Cluster loader for cluster {object.cluster} not found") from None

        return await cluster_loader.list_pods(object)
