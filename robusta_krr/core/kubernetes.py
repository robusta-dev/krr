import asyncio
import itertools

from kubernetes import client, config
from kubernetes.client.models import V1PodList, V1DeploymentList, V1Container, V1StatefulSetList

from robusta_krr.core.objects import K8sObjectData
from robusta_krr.core.result import ResourceAllocations
from robusta_krr.utils.configurable import Configurable


class ClusterLoader(Configurable):
    def __init__(self, cluster: str, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.cluster = cluster
        self.v1 = client.AppsV1Api(api_client=config.new_client_from_config(context=cluster))

    async def list_scannable_objects(self) -> list[tuple[V1Container, K8sObjectData]]:
        """List all scannable objects.

        Returns:
            A list of scannable objects.
        """

        self.debug("Listing scannable objects")

        try:
            objects_tuple = await asyncio.gather(
                self._list_deployments(),
                self._list_all_statefulsets(),
                self._list_all_daemon_set(),
                # self._list_all_jobs(),
            )
        except Exception as e:
            self.error(f"Error trying to list pods in cluster {self.cluster}: {e}")
            return []

        return list(itertools.chain(*objects_tuple))

    async def _list_deployments(self) -> list[tuple[V1Container, K8sObjectData]]:
        ret: V1DeploymentList = await asyncio.to_thread(self.v1.list_deployment_for_all_namespaces, watch=False)

        return [
            (
                container,
                K8sObjectData(
                    cluster=self.cluster,
                    namespace=item.metadata.namespace,
                    name=item.metadata.name,
                    kind="Deployment",
                    container=container.name,
                ),
            )
            for item in ret.items
            for container in item.spec.template.spec.containers
        ]

    async def _list_all_statefulsets(self) -> list[tuple[V1Container, K8sObjectData]]:
        ret: V1StatefulSetList = await asyncio.to_thread(self.v1.list_stateful_set_for_all_namespaces, watch=False)

        return [
            (
                container,
                K8sObjectData(
                    cluster=self.cluster,
                    namespace=item.metadata.namespace,
                    name=item.metadata.name,
                    kind="StatefulSet",
                    container=container.name,
                ),
            )
            for item in ret.items
            for container in item.spec.template.spec.containers
        ]

    async def _list_all_daemon_set(self) -> list[tuple[V1Container, K8sObjectData]]:
        ret: V1StatefulSetList = await asyncio.to_thread(self.v1.list_daemon_set_for_all_namespaces, watch=False)

        return [
            (
                container,
                K8sObjectData(
                    cluster=self.cluster,
                    namespace=item.metadata.namespace,
                    name=item.metadata.name,
                    kind="DaemonSet",
                    container=container.name,
                ),
            )
            for item in ret.items
            for container in item.spec.template.spec.containers
        ]

    async def _list_all_jobs(self) -> list[tuple[V1Container, K8sObjectData]]:
        """Not working yet."""

        ret: V1StatefulSetList = await asyncio.to_thread(self.v1.list_, watch=False)

        return [
            (
                container,
                K8sObjectData(
                    cluster=self.cluster,
                    namespace=item.metadata.namespace,
                    name=item.metadata.name,
                    kind="Job",
                    container=container.name,
                ),
            )
            for item in ret.items
            for container in item.spec.template.spec.containers
        ]

    async def _list_pods(self) -> list[tuple[V1Container, K8sObjectData]]:
        """For future use, not supported yet."""

        ret: V1PodList = await asyncio.to_thread(self.v1.list_pod_for_all_namespaces, watch=False)

        return [
            (
                container,
                K8sObjectData(
                    cluster=self.cluster,
                    namespace=item.metadata.namespace,
                    name=item.metadata.name,
                    kind="Pod",
                    container=container.name,
                ),
            )
            for item in ret.items
            for container in item.spec.containers
        ]


class KubernetesLoader(Configurable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.debug("Initializing Kubernetes client")
        config.load_kube_config()

        self._kubernetes_object_allocation_cache: dict[K8sObjectData, ResourceAllocations] = {}

    async def list_clusters(self) -> list[str]:
        """List all clusters.

        Returns:
            A list of clusters.
        """

        self.debug("Listing clusters")

        contexts, _ = await asyncio.to_thread(config.list_kube_config_contexts)

        return [context["name"] for context in contexts]

    async def list_scannable_objects(self, clusters: list[str]) -> list[K8sObjectData]:
        """List all scannable objects.

        Returns:
            A list of scannable objects.
        """

        self.debug("Listing scannable objects")

        cluster_loaders = [ClusterLoader(cluster=cluster, config=self.config) for cluster in clusters]
        objects_res = await asyncio.gather(
            *[cluster_loader.list_scannable_objects() for cluster_loader in cluster_loaders]
        )
        objects = list(itertools.chain(*objects_res))

        for container, obj in objects:
            self._kubernetes_object_allocation_cache[obj] = ResourceAllocations.from_container(container)

        return [obj for _, obj in objects]

    async def get_object_current_recommendations(self, object: K8sObjectData) -> ResourceAllocations:
        """Get the current recommendations for a given object.

        Args:
            object: The object to get the recommendations for.

        Returns:
            The current recommendations for the object.
        """

        self.debug(f"Getting current recommendations for {object}")

        return self._kubernetes_object_allocation_cache[object]
