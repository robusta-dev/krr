import asyncio

from robusta_krr.core.objects import K8sObjectData
from robusta_krr.core.result import ResourceAllocations
from robusta_krr.utils.configurable import Configurable


# TODO: We need a way to connect to both being in the cluster and outside of a cluster
class KubernetesLoader(Configurable):
    # TODO: This is just a mock data for now, implement this later
    async def list_scannable_objects(self) -> list[K8sObjectData]:
        """List all scannable objects.

        Returns:
            A list of scannable objects.
        """

        self.debug("Listing scannable objects")
        await asyncio.sleep(2.5)  # Simulate a slow API call

        return [
            K8sObjectData(name="prometheus", kind="Deployment", namespace="default"),
            K8sObjectData(name="grafana", kind="Deployment", namespace="default"),
            K8sObjectData(name="alertmanager", kind="Deployment", namespace="default"),
            K8sObjectData(name="robusta-runner", kind="Deployment", namespace="default"),
            K8sObjectData(name="robusta-forwarder", kind="Deployment", namespace="default"),
        ]

    # TODO: This is just a mock data for now, implement this later
    async def get_object_current_recommendations(self, object: K8sObjectData) -> ResourceAllocations:
        from robusta_krr.core.result import ResourceType

        self.debug(f"Getting current recommendations for {object}")
        await asyncio.sleep(1.5)  # Simulate a slow API call

        return ResourceAllocations(
            requests={ResourceType.CPU: 30, ResourceType.Memory: 300},
            limits={ResourceType.CPU: 50, ResourceType.Memory: 600},
        )
