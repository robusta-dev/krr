import abc
from typing import Optional
from robusta_krr.core.models.objects import K8sWorkload, PodData


class BaseWorkloadLoader(abc.ABC):
    @abc.abstractmethod
    async def list_workloads(self) -> list[K8sWorkload]:
        pass

    @abc.abstractmethod
    async def list_pods(self, object: K8sWorkload) -> list[PodData]:
        pass
