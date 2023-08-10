import datetime
from abc import ABC, abstractmethod

from robusta_krr.core.abstract.strategies import PodsTimeData
from robusta_krr.core.models.objects import K8sObjectData


class BaseMetric(ABC):
    """
    This abstraction is done for a future use.
    Currently we only scrape metrics from Prometheus,
    but in the future we may want to support other metric sources like Datadog, etc.

    TODO: When we want to support other metric sources, we should maybe rethink an interface here.
    """

    @abstractmethod
    async def load_data(
        self, object: K8sObjectData, period: datetime.timedelta, step: datetime.timedelta
    ) -> PodsTimeData:
        ...
