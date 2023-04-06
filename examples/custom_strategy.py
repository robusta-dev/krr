# This is an example on how to create your own custom strategy

from decimal import Decimal

import pydantic as pd

from robusta_krr import run
from robusta_krr.core.abstract.strategies import (
    BaseStrategy,
    HistoryData,
    K8sObjectData,
    ResourceRecommendation,
    ResourceType,
    RunResult,
    StrategySettings,
)


class CustomStrategySettings(StrategySettings):
    cpu_percentile: Decimal = pd.Field(99, gt=0, description="The percentile to use for the request recommendation.")
    memory_percentile: Decimal = pd.Field(
        105, gt=0, description="The percentile to use for the request recommendation."
    )


class CustomStrategy(BaseStrategy[CustomStrategySettings]):
    __display_name__ = "custom"

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
            return Decimal("NaN")

        return max(data_) * percentile / 100


# Running this file will register the strategy and make it available to the CLI
if __name__ == "__main__":
    run()
