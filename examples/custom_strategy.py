# This is an example on how to create your own custom strategy

import pydantic as pd

import robusta_krr
from robusta_krr.api.models import K8sObjectData, MetricsPodData, ResourceRecommendation, ResourceType, RunResult
from robusta_krr.api.strategies import BaseStrategy, StrategySettings
from robusta_krr.core.integrations.prometheus.metrics import MaxMemoryLoader, PercentileCPULoader


# Providing description to the settings will make it available in the CLI help
class CustomStrategySettings(StrategySettings):
    param_1: float = pd.Field(99, gt=0, description="First example parameter")
    param_2: float = pd.Field(105_000, gt=0, description="Second example parameter")


class CustomStrategy(BaseStrategy[CustomStrategySettings]):
    """
    A custom strategy that uses the provided parameters for CPU and memory.
    Made only in order to demonstrate how to create a custom strategy.
    """

    display_name = "custom"  # The name of the strategy
    rich_console = True  # Whether to use rich console for the CLI
    metrics = [PercentileCPULoader(90), MaxMemoryLoader]  # The metrics to use for the strategy

    def run(self, history_data: MetricsPodData, object_data: K8sObjectData) -> RunResult:
        return {
            ResourceType.CPU: ResourceRecommendation(request=self.settings.param_1, limit=None),
            ResourceType.Memory: ResourceRecommendation(request=self.settings.param_2, limit=self.settings.param_2),
        }


# Running this file will register the strategy and make it available to the CLI
# Run it as `python ./custom_strategy.py my_strategy`
if __name__ == "__main__":
    robusta_krr.run()
