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

    async def list_scannable_objects(self) -> list[K8sObjectData]:
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
                # self._list_all_jobs(),  # TODO: Add support for Jobs
            )
        except Exception as e:
            self.error(f"Error trying to list pods in cluster {self.cluster}: {e}")
            return []

        return list(itertools.chain(*objects_tuple))

    async def _list_deployments(self) -> list[K8sObjectData]:
        ret: V1DeploymentList = await asyncio.to_thread(self.v1.list_deployment_for_all_namespaces, watch=False)

        return [
            K8sObjectData(
                cluster=self.cluster,
                namespace=item.metadata.namespace,
                name=item.metadata.name,
                kind="Deployment",
                container=container.name,
                allocations=ResourceAllocations.from_container(container),
            )
            for item in ret.items
            for container in item.spec.template.spec.containers
        ]

    async def _list_all_statefulsets(self) -> list[K8sObjectData]:
        ret: V1StatefulSetList = await asyncio.to_thread(self.v1.list_stateful_set_for_all_namespaces, watch=False)

        return [
            K8sObjectData(
                cluster=self.cluster,
                namespace=item.metadata.namespace,
                name=item.metadata.name,
                kind="StatefulSet",
                container=container.name,
                allocations=ResourceAllocations.from_container(container),
            )
            for item in ret.items
            for container in item.spec.template.spec.containers
        ]

    async def _list_all_daemon_set(self) -> list[K8sObjectData]:
        ret: V1StatefulSetList = await asyncio.to_thread(self.v1.list_daemon_set_for_all_namespaces, watch=False)

        return [
            K8sObjectData(
                cluster=self.cluster,
                namespace=item.metadata.namespace,
                name=item.metadata.name,
                kind="DaemonSet",
                container=container.name,
                allocations=ResourceAllocations.from_container(container),
            )
            for item in ret.items
            for container in item.spec.template.spec.containers
        ]

    async def _list_all_jobs(self) -> list[K8sObjectData]:
        """Not working yet."""

        ret: V1StatefulSetList = await asyncio.to_thread(self.v1.list_, watch=False)

        return [
            K8sObjectData(
                cluster=self.cluster,
                namespace=item.metadata.namespace,
                name=item.metadata.name,
                kind="Job",
                container=container.name,
                allocations=ResourceAllocations.from_container(container),
            )
            for item in ret.items
            for container in item.spec.template.spec.containers
        ]

    async def _list_pods(self) -> list[K8sObjectData]:
        """For future use, not supported yet."""

        ret: V1PodList = await asyncio.to_thread(self.v1.list_pod_for_all_namespaces, watch=False)

        return [
            K8sObjectData(
                cluster=self.cluster,
                namespace=item.metadata.namespace,
                name=item.metadata.name,
                kind="Pod",
                container=container.name,
                allocations=ResourceAllocations.from_container(container),
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
        objects = await asyncio.gather(*[cluster_loader.list_scannable_objects() for cluster_loader in cluster_loaders])
        return list(itertools.chain(*objects))
