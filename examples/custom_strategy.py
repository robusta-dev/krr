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
    param_1: Decimal = pd.Field(99, gt=0, description="First example parameter")
    param_2: Decimal = pd.Field(105_000, gt=0, description="Second example parameter")


class CustomStrategy(BaseStrategy[CustomStrategySettings]):
    __display_name__ = "custom"

    def run(self, history_data: HistoryData, object_data: K8sObjectData) -> RunResult:
        return {
            ResourceType.CPU: ResourceRecommendation(request=self.settings.param_1, limit=None),
            ResourceType.Memory: ResourceRecommendation(request=self.settings.param_2, limit=self.settings.param_2),
        }


# Running this file will register the strategy and make it available to the CLI
if __name__ == "__main__":
    run()
