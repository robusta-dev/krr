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
    cpu_percentile: Decimal = pd.Field(99, gt=0, description="The percentile to use for the request recommendation.")
    memory_percentile: Decimal = pd.Field(
        105, gt=0, description="The percentile to use for the request recommendation."
    )


class SimpleStrategy(BaseStrategy[SimpleStrategySettings]):
    __display_name__ = "simple"

    def run(self, history_data: HistoryData, object_data: K8sObjectData) -> RunResult:
        cpu_usage = self._calculate_percentile(history_data[ResourceType.CPU], self.settings.cpu_percentile)
        memory_usage = self._calculate_percentile(history_data[ResourceType.Memory], self.settings.memory_percentile)

        return {
            ResourceType.CPU: ResourceRecommendation(request=cpu_usage, limit=None),
            ResourceType.Memory: ResourceRecommendation(request=memory_usage, limit=memory_usage),
        }

    def _calculate_percentile(self, data: dict[str, list[Decimal]], percentile: Decimal) -> Decimal:
        data_ = [value for values in data.values() for value in values]
        if len(data_) == 0:
            return Decimal.from_float(float("nan"))

        min_val, max_val = min(data_), max(data_)
        # If the min and max are the same, we can't calculate a percentile
        # Should'n happen on practice, but just in case
        if min_val == max_val:
            return min_val

        return min_val + (max_val - min_val) * percentile / 100
