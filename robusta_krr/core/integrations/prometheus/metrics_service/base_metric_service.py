import datetime
from typing import Optional
import abc
from robusta_krr.core.abstract.strategies import ResourceHistoryData
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.core.models.result import ResourceType
from robusta_krr.utils.configurable import Configurable
from kubernetes.client.api_client import ApiClient


class MetricsService(Configurable, abc.ABC):
    def __init__(self, config: Config, api_client: Optional[ApiClient] = None, cluster: Optional[str] = None,) -> None:
        super().__init__(config=config)
        self.api_client = api_client
        self.cluster = cluster or 'default'
    
    @abc.abstractmethod
    def check_connection(self):
        ...

    @abc.abstractmethod
    def name(self) -> str:
        ...

    @abc.abstractmethod
    async def gather_data(
        self,
        object: K8sObjectData,
        resource: ResourceType,
        period: datetime.timedelta,
        *,
        step: datetime.timedelta = datetime.timedelta(minutes=30),
    ) -> ResourceHistoryData:
        ...