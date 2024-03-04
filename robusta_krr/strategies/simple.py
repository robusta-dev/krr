import numpy as np
import pydantic as pd

from robusta_krr.core.abstract.strategies import (
    BaseStrategy,
    K8sObjectData,
    MetricsPodData,
    PodsTimeData,
    ResourceRecommendation,
    ResourceType,
    RunResult,
    StrategySettings,
)
from robusta_krr.core.integrations.prometheus.metrics import (
    CPUAmountLoader,
    MaxMemoryLoader,
    MemoryAmountLoader,
    PercentileCPULoader,
    PrometheusMetric,
)


class SimpleStrategySettings(StrategySettings):
    cpu_percentile: float = pd.Field(99, gt=0, le=100, description="The percentile to use for the CPU recommendation.")
    memory_buffer_percentage: float = pd.Field(
        15, gt=0, description="The percentage of added buffer to the peak memory usage for memory recommendation."
    )
    points_required: int = pd.Field(
        100, ge=1, description="The number of data points required to make a recommendation for a resource."
    )

    def calculate_memory_proposal(self, data: PodsTimeData) -> float:
        data_ = [np.max(values[:, 1]) for values in data.values()]
        if len(data_) == 0:
            return float("NaN")

        return np.max(data_) * (1 + self.memory_buffer_percentage / 100)

    def calculate_cpu_proposal(self, data: PodsTimeData) -> float:
        if len(data) == 0:
            return float("NaN")

        if len(data) > 1:
            data_ = np.concatenate([values[:, 1] for values in data.values()])
        else:
            data_ = list(data.values())[0][:, 1]

        return np.max(data_)


class SimpleStrategy(BaseStrategy[SimpleStrategySettings]):
    """
    CPU request: {cpu_percentile}% percentile, limit: unset
    Memory request: max + {memory_buffer_percentage}%, limit: max + {memory_buffer_percentage}%
    History: {history_duration} hours
    Step: {timeframe_duration} minutes

    All parameters can be customized. For example: `krr simple --cpu_percentile=90 --memory_buffer_percentage=15 --history_duration=24 --timeframe_duration=0.5`

    This strategy does not work with objects with HPA defined (Horizontal Pod Autoscaler).
    If HPA is defined for CPU or Memory, the strategy will return "?" for that resource.

    Learn more: [underline]https://github.com/robusta-dev/krr#algorithm[/underline]
    """

    display_name = "simple"
    rich_console = True

    @property
    def metrics(self) -> list[type[PrometheusMetric]]:
        return [PercentileCPULoader(self.settings.cpu_percentile), MaxMemoryLoader, CPUAmountLoader, MemoryAmountLoader]

    def __calculate_cpu_proposal(
        self, history_data: MetricsPodData, object_data: K8sObjectData
    ) -> ResourceRecommendation:
        data = history_data["PercentileCPULoader"]

        if len(data) == 0:
            return ResourceRecommendation.undefined(info="No data")

        data_count = {pod: values[0, 1] for pod, values in history_data["CPUAmountLoader"].items()}
        # Here we filter out pods from calculation that have less than `points_required` data points
        filtered_data = {
            pod: values for pod, values in data.items() if data_count.get(pod, 0) >= self.settings.points_required
        }

        if len(filtered_data) == 0:
            return ResourceRecommendation.undefined(info="Not enough data")

        if object_data.hpa is not None and object_data.hpa.target_cpu_utilization_percentage is not None:
            return ResourceRecommendation.undefined(info="HPA detected")

        cpu_usage = self.settings.calculate_cpu_proposal(filtered_data)
        return ResourceRecommendation(request=cpu_usage, limit=None)

    def __calculate_memory_proposal(
        self, history_data: MetricsPodData, object_data: K8sObjectData
    ) -> ResourceRecommendation:
        data = history_data["MaxMemoryLoader"]

        if len(data) == 0:
            return ResourceRecommendation.undefined(info="No data")

        data_count = {pod: values[0, 1] for pod, values in history_data["MemoryAmountLoader"].items()}
        # Here we filter out pods from calculation that have less than `points_required` data points
        filtered_data = {
            pod: value for pod, value in data.items() if data_count.get(pod, 0) >= self.settings.points_required
        }

        if len(filtered_data) == 0:
            return ResourceRecommendation.undefined(info="Not enough data")

        if object_data.hpa is not None and object_data.hpa.target_memory_utilization_percentage is not None:
            return ResourceRecommendation.undefined(info="HPA detected")

        memory_usage = self.settings.calculate_memory_proposal(filtered_data)
        return ResourceRecommendation(request=memory_usage, limit=memory_usage)

    def run(self, history_data: MetricsPodData, object_data: K8sObjectData) -> RunResult:
        return {
            ResourceType.CPU: self.__calculate_cpu_proposal(history_data, object_data),
            ResourceType.Memory: self.__calculate_memory_proposal(history_data, object_data),
        }
