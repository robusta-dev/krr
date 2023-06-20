import numpy as np
import pydantic as pd
from numpy.typing import NDArray

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
    cpu_percentile: float = pd.Field(99, gt=0, le=100, description="The percentile to use for the CPU recommendation.")
    memory_buffer_percentage: float = pd.Field(
        5, gt=0, description="The percentage of added buffer to the peak memory usage for memory recommendation."
    )

    def calculate_memory_proposal(self, data: dict[str, NDArray[np.float64]]) -> float:
        data_ = [np.max(values[:, 1]) for values in data.values()]
        if len(data_) == 0:
            return float("NaN")

        return max(data_) * (1 + self.memory_buffer_percentage / 100)

    def calculate_cpu_proposal(self, data: dict[str, NDArray[np.float64]]) -> float:
        if len(data) == 0:
            return float("NaN")

        if len(data) > 1:
            data_ = np.concatenate([values[:, 1] for values in data.values()])
        else:
            data_ = list(data.values())[0][:, 1]

        return np.percentile(data_, self.cpu_percentile)


class SimpleStrategy(BaseStrategy[SimpleStrategySettings]):
    """
    CPU request: {cpu_percentile}% percentile, limit: unset
    Memory request: max + {memory_buffer_percentage}%, limit: max + {memory_buffer_percentage}%
    Learn more: [underline]https://github.com/robusta-dev/krr#algorithm[/underline]
    """

    __display_name__ = "simple"
    __rich_console__ = True

    def run(self, history_data: HistoryData, object_data: K8sObjectData) -> RunResult:
        cpu_usage = self.settings.calculate_cpu_proposal(history_data[ResourceType.CPU].data)
        memory_usage = self.settings.calculate_memory_proposal(history_data[ResourceType.Memory].data)

        return {
            ResourceType.CPU: ResourceRecommendation(request=cpu_usage, limit=None),
            ResourceType.Memory: ResourceRecommendation(request=memory_usage, limit=memory_usage),
        }
