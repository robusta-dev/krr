import asyncio
import datetime
import random

from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.core.models.result import ResourceType
from robusta_krr.core.abstract.strategies import HistoryData
from robusta_krr.utils.configurable import Configurable


class PrometheusLoader(Configurable):
    async def gather_data(
        self,
        object: K8sObjectData,
        resource: ResourceType,
        period: datetime.timedelta,
        *,
        timeframe: datetime.timedelta = datetime.timedelta(minutes=1),
    ) -> HistoryData:
        # TODO: This is mock function. Implement this later using the Prometheus API
        self.debug(f"Gathering data for {object} and {resource} for the last {period}")
        await asyncio.sleep(1.5)  # Simulate a slow API call
        points = int(period / timeframe)
        return {
            "container_1": [random.randrange(30, 300) for _ in range(points)],
            "container_2": [random.randrange(70, 500) for _ in range(points)],
        }
