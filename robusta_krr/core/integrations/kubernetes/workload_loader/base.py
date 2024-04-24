import abc
from robusta_krr.core.models.objects import K8sWorkload, PodData


class BaseWorkloadLoader(abc.ABC):
    """A base class for workload loaders."""

    @abc.abstractmethod
    async def list_workloads(self) -> list[K8sWorkload]:
        pass


class IListPodsFallback(abc.ABC):
    """This is an interface that a workload loader can implement to have a fallback method to list pods."""

    @abc.abstractmethod
    async def list_pods(self, object: K8sWorkload) -> list[PodData]:
        pass
