from decimal import Decimal

import pydantic as pd

from robusta_krr.core.abstract.strategies import (
    BaseStrategy,
    HistoryData,
    K8sObjectData,
    ResourceRecommendation,
    ResourceType,
    RunResult,
    StrategySettings,
)


class SimpleStrategySettings(StrategySettings):
    request_percentile: float = pd.Field(
        0.9, gt=0, le=1, description="The percentile to use for the request recommendation."
    )
    limit_percentile: float = pd.Field(
        0.99, gt=0, le=1, description="The percentile to use for the limit recommendation."
    )


class SimpleStrategy(BaseStrategy[SimpleStrategySettings]):
    __display_name__ = "simple"

    def run(self, history_data: HistoryData, object_data: K8sObjectData) -> RunResult:
        cpu_usage = self._calculate_percentile(history_data[ResourceType.CPU], self.settings.request_percentile)
        memory_usage = self._calculate_percentile(history_data[ResourceType.Memory], self.settings.request_percentile)

        return {
            ResourceType.CPU: ResourceRecommendation(
                request=Decimal(cpu_usage) / 1000 if cpu_usage is not None else None,
                limit=None,
            ),
            ResourceType.Memory: ResourceRecommendation(
                request=Decimal(memory_usage),
                limit=Decimal(memory_usage),
            ),
        }

    def _calculate_percentile(self, data: list[float], percentile: float) -> float:
        if len(data) == 0:
            return float("nan")

        data = sorted(data)
        return data[int(len(data) * percentile)]
