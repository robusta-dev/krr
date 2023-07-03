import abc
from typing import Optional

from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.utils.configurable import Configurable

class WorkloadLoader(Configurable, abc.ABC):

    @abc.abstractmethod
    async def list_scannable_objects(self, clusters: Optional[list[str]]) -> list[K8sObjectData]:
        ...
    
    @abc.abstractmethod
    async def list_clusters(self) -> Optional[list[str]]:
        ...