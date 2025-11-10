import abc
import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Any

from kubernetes.client.api_client import ApiClient

from robusta_krr.core.abstract.strategies import PodsTimeData
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import K8sObjectData

from ..metrics import PrometheusMetric


class MetricsService(abc.ABC):
    def __init__(
        self,
        api_client: Optional[ApiClient] = None,
        cluster: Optional[str] = None,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        self.api_client = api_client
        self.cluster = cluster or "default"
        self.executor = executor

    @abc.abstractmethod
    def check_connection(self):
        ...

    @classmethod
    def name(cls) -> str:
        classname = cls.__name__
        return classname.replace("MetricsService", "") if classname != MetricsService.__name__ else classname

    @abc.abstractmethod
    def get_cluster_names(self) -> Optional[List[str]]:
        ...

    @abc.abstractmethod
    async def get_cluster_summary(self) -> Dict[str, Any]:
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
        if settings.prometheus_cluster_label is None:
            return ""
        return f', {settings.prometheus_label}="{settings.prometheus_cluster_label}"'
