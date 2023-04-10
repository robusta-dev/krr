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
    cpu_percentile: Decimal = pd.Field(
        99, gt=0, le=100, description="The percentile to use for the CPU recommendation."
    )
    memory_buffer_percentage: Decimal = pd.Field(
        5, gt=0, description="The percentage of added buffer to the peak memory usage for memory recommendation."
    )

    def calculate_memory_proposal(self, data: dict[str, list[Decimal]]) -> Decimal:
        data_ = [value for values in data.values() for value in values]
        if len(data_) == 0:
            return Decimal("NaN")

        return max(data_) * Decimal(1 + self.memory_buffer_percentage / 100)

    def calculate_cpu_proposal(self, data: dict[str, list[Decimal]]) -> Decimal:
        data_ = [value for values in data.values() for value in values]
        if len(data_) == 0:
            return Decimal("NaN")

        return data_[int((len(data_) - 1) * self.cpu_percentile / 100)]


class SimpleStrategy(BaseStrategy[SimpleStrategySettings]):
    __display_name__ = "simple"

    def run(self, history_data: HistoryData, object_data: K8sObjectData) -> RunResult:
        cpu_usage = self.settings.calculate_cpu_proposal(history_data[ResourceType.CPU])
        memory_usage = self.settings.calculate_memory_proposal(history_data[ResourceType.Memory])

        return {
            ResourceType.CPU: ResourceRecommendation(request=cpu_usage, limit=None),
            ResourceType.Memory: ResourceRecommendation(request=memory_usage, limit=memory_usage),
        }
