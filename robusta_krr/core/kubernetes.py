import asyncio

from kubernetes import client, config

from robusta_krr.core.objects import K8sObjectData
from robusta_krr.core.result import ResourceAllocations
from robusta_krr.utils.configurable import Configurable


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

    async def list_scannable_objects(self, cluster: str) -> list[K8sObjectData]:
        """List all scannable objects.

        Returns:
            A list of scannable objects.
        """

        self.debug("Listing scannable objects")

        v1 = client.CoreV1Api(api_client=config.new_client_from_config(context=cluster))
        try:
            ret = await asyncio.to_thread(v1.list_pod_for_all_namespaces, watch=False)
        except Exception as e:
            self.error(f"Error trying to list pods in cluster {cluster}: {e}")
            return []

        objects = [
            (
                item,
                container,
                K8sObjectData(
                    cluster=cluster,
                    namespace=item.metadata.namespace,
                    name=item.metadata.name,
                    kind="Pod",
                    container=container.name,
                ),
            )
            for item in ret.items
            for container in item.spec.containers
        ]

        for _, container, obj in objects:
            self.debug(f"Found scannable object {obj}")
            self._kubernetes_object_allocation_cache[obj] = ResourceAllocations.from_container(container)

        return [obj for _, _, obj in objects]

    async def get_object_current_recommendations(self, object: K8sObjectData) -> ResourceAllocations:
        """Get the current recommendations for a given object.

        Args:
            object: The object to get the recommendations for.

        Returns:
            The current recommendations for the object.
        """

        self.debug(f"Getting current recommendations for {object}")

        return self._kubernetes_object_allocation_cache[object]
