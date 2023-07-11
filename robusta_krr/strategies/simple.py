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

    This strategy does not work with objects with HPA defined (Horizontal Pod Autoscaler).
    If HPA is defined for CPU or Memory, the strategy will return "?" for that resource.

    Learn more: [underline]https://github.com/robusta-dev/krr#algorithm[/underline]
    """

    __display_name__ = "simple"
    __rich_console__ = True

    def __calculate_cpu_proposal(self, history_data: HistoryData, object_data: K8sObjectData) -> ResourceRecommendation:
        if len(history_data[ResourceType.CPU].data) == 0:
            return ResourceRecommendation.undefined(info="No data")

        if object_data.hpa is not None and object_data.hpa.target_cpu_utilization_percentage is not None:
            return ResourceRecommendation.undefined(info="HPA detected")

        cpu_usage = self.settings.calculate_cpu_proposal(history_data[ResourceType.CPU].data)
        return ResourceRecommendation(request=cpu_usage, limit=None)

    def __calculate_memory_proposal(
        self, history_data: HistoryData, object_data: K8sObjectData
    ) -> ResourceRecommendation:
        if len(history_data[ResourceType.Memory].data) == 0:
            return ResourceRecommendation.undefined(info="No data")

        if object_data.hpa is not None and object_data.hpa.target_memory_utilization_percentage is not None:
            return ResourceRecommendation.undefined(info="HPA detected")

        memory_usage = self.settings.calculate_memory_proposal(history_data[ResourceType.Memory].data)
        return ResourceRecommendation(request=memory_usage, limit=memory_usage)

    def run(self, history_data: HistoryData, object_data: K8sObjectData) -> RunResult:
        return {
            ResourceType.CPU: self.__calculate_cpu_proposal(history_data, object_data),
            ResourceType.Memory: self.__calculate_memory_proposal(history_data, object_data),
        }
