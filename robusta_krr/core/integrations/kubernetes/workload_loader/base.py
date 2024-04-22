import abc
from typing import Optional
from robusta_krr.core.models.objects import K8sWorkload, PodData


class BaseWorkloadLoader(abc.ABC):
    def __init__(self, cluster: Optional[str] = None) -> None:
        self.cluster = cluster

    @abc.abstractmethod
    async def list_workloads(self, clusters: Optional[list[str]]) -> list[K8sWorkload]:
        pass

    @abc.abstractmethod
    async def list_pods(self, object: K8sWorkload) -> list[PodData]:
        pass
