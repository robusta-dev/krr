import abc
import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from kubernetes.client.api_client import ApiClient

from robusta_krr.core.abstract.strategies import PodsTimeData
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import K8sWorkload

from ..metrics import PrometheusMetric


class MetricsService(abc.ABC):
    @abc.abstractmethod
    def check_connection(self):
        pass

    @abc.abstractmethod
    def get_cluster_names(self) -> Optional[List[str]]:
        pass

    @abc.abstractmethod
    async def gather_data(
        self,
        object: K8sWorkload,
        LoaderClass: type[PrometheusMetric],
        period: datetime.timedelta,
        step: datetime.timedelta = datetime.timedelta(minutes=30),
    ) -> PodsTimeData:
        pass

    @classmethod
    def name(cls) -> str:
        classname = cls.__name__
        return classname.replace("MetricsService", "") if classname != MetricsService.__name__ else classname

    def get_prometheus_cluster_label(self) -> str:
        """
        Generates the cluster label for querying a centralized Prometheus

        Returns:
        str: a promql safe label string for querying the cluster.
        """
        if settings.prometheus_cluster_label is None:
            return ""
        return f', {settings.prometheus_label}="{settings.prometheus_cluster_label}"'
