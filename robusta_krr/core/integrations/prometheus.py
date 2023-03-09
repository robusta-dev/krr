import datetime
import random

from robusta_krr.core.models.objects import K8sObjectData
from robusta_krr.core.models.result import ResourceType
from robusta_krr.utils.configurable import Configurable


class PrometheusLoader(Configurable):
    async def gather_data(
        self,
        object: K8sObjectData,
        resource: ResourceType,
        period: datetime.timedelta,
        *,
        timeframe: datetime.timedelta = datetime.timedelta(minutes=1),
    ) -> list[int]:
        # TODO: This is mock function. Implement this later using the Prometheus API
        self.debug(f"Gathering data for {object} and {resource} for the last {period}")
        points = int(period / timeframe)

        if resource == ResourceType.CPU:
            return [random.randrange(1, 3000) for _ in range(points)]
        elif resource == ResourceType.Memory:
            return [random.randrange(70_000_000, 5_000_000_000) for _ in range(points)]
        else:
            raise ValueError(f"Unknown resource type: {resource}")
