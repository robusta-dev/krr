import abc
import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from kubernetes.client.api_client import ApiClient

from robusta_krr.core.abstract.strategies import PodsTimeData
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.utils.configurable import Configurable

from ..metrics import PrometheusMetric


class MetricsService(Configurable, abc.ABC):
    def __init__(
        self,
        config: Config,
        api_client: Optional[ApiClient] = None,
        cluster: Optional[str] = None,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        super().__init__(config=config)
        self.api_client = api_client
        self.cluster = cluster or "default"
        self.executor = executor

    @abc.abstractmethod
    def check_connection(self):
        ...

    @property
    def name(self) -> str:
        classname = self.__class__.__name__
        return classname.replace("MetricsService", "") if classname != MetricsService.__name__ else classname

    @abc.abstractmethod
    def get_cluster_names(self) -> Optional[List[str]]:
        ...

    @abc.abstractmethod
    async def gather_data(
        self,
        object: K8sObjectData,
        LoaderClass: type[PrometheusMetric],
        period: datetime.timedelta,
        step: datetime.timedelta = datetime.timedelta(minutes=30),
    ) -> PodsTimeData:
        ...

    def get_prometheus_cluster_label(self) -> str:
        """
        Generates the cluster label for querying a centralized Prometheus

        Returns:
        str: a promql safe label string for querying the cluster.
        """
        if self.config.prometheus_cluster_label is None:
            return ""
        return f', {self.config.prometheus_label}="{self.config.prometheus_cluster_label}"'
