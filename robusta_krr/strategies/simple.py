"""
    This strategy is a version of a simple strategy that we might want to set as a default strategy for the user.
    It is the same as the simple strategy, but it also uses OOMKilled events and memory limits to calculate memory recommendations.
    Currently, it is in a testing mode and may not work as expected.
"""

from datetime import timedelta

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
    MaxOOMKilledMemoryLoader,
)


class SimpleStrategySettings(StrategySettings):
    cpu_percentile: float = pd.Field(99, gt=0, le=100, description="The percentile to use for the CPU recommendation.")
    memory_buffer_percentage: float = pd.Field(
        15, gt=0, description="The percentage of added buffer to the peak memory usage for memory recommendation."
    )
    points_required: int = pd.Field(
        100, ge=1, description="The number of data points required to make a recommendation for a resource."
    )
    allow_hpa: bool = pd.Field(
        False,
        description="Whether to calculate recommendations even when there is an HPA scaler defined on that resource.",
    )
    use_oomkill_data: bool = pd.Field(
        False,
        description="Whether to use OOMKilled data to calculate memory recommendations (experimental).",
    )
    oom_memory_buffer_percentage: float = pd.Field(
        25, gt=0, description="The percentage of added buffer to the max memory limit surpassed by OOMKilled event."
    )

    def calculate_memory_proposal(self, data: PodsTimeData, max_oomkill: float = 0) -> float:
        data_ = [np.max(values[:, 1]) for values in data.values()]
        if len(data_) == 0:
            return float("NaN")

        return max(
            np.max(data_) * (1 + self.memory_buffer_percentage / 100),
            max_oomkill * (1 + self.oom_memory_buffer_percentage / 100),
        )

    def calculate_cpu_proposal(self, data: PodsTimeData) -> float:
        if len(data) == 0:
            return float("NaN")

        if len(data) > 1:
            data_ = np.concatenate([values[:, 1] for values in data.values()])
        else:
            data_ = list(data.values())[0][:, 1]

        return np.max(data_)

    def history_range_enough(self, history_range: tuple[timedelta, timedelta]) -> bool:
        start, end = history_range
        return (end - start) >= timedelta(hours=3)


class SimpleStrategy(BaseStrategy[SimpleStrategySettings]):
    """
    CPU request: {cpu_percentile}% percentile, limit: unset
    Memory request: max + {memory_buffer_percentage}%, limit: max + {memory_buffer_percentage}%
    History: {history_duration} hours
    Step: {timeframe_duration} minutes

    All parameters can be customized. For example: `krr simple --cpu_percentile=90 --memory_buffer_percentage=15 --history_duration=24 --timeframe_duration=0.5`

    This strategy does not work with objects with HPA defined (Horizontal Pod Autoscaler).
    If HPA is defined for CPU or Memory, the strategy will return "?" for that resource.
    You can override this behaviour by passing the --allow-hpa flag

    Learn more: [underline]https://github.com/robusta-dev/krr#algorithm[/underline]
    """

    display_name = "simple"
    rich_console = True

    @property
    def metrics(self) -> list[type[PrometheusMetric]]:
        metrics = [
            PercentileCPULoader(self.settings.cpu_percentile),
            MaxMemoryLoader,
            CPUAmountLoader,
            MemoryAmountLoader,
        ]

        if self.settings.use_oomkill_data:
            metrics.append(MaxOOMKilledMemoryLoader)

        return metrics

    def __calculate_cpu_proposal(
        self, history_data: MetricsPodData, object_data: K8sObjectData
    ) -> ResourceRecommendation:
        data = history_data["PercentileCPULoader"]

        if len(data) == 0:
            return ResourceRecommendation.undefined(info="No data")

        data_count = {pod: values[0, 1] for pod, values in history_data["CPUAmountLoader"].items()}
        total_points_count = sum(data_count.values())

        if total_points_count < self.settings.points_required:
            return ResourceRecommendation.undefined(info="Not enough data")

        if (
            object_data.hpa is not None
            and object_data.hpa.target_cpu_utilization_percentage is not None
            and not self.settings.allow_hpa
        ):
            return ResourceRecommendation.undefined(info="HPA detected")

        cpu_usage = self.settings.calculate_cpu_proposal(data)
        return ResourceRecommendation(request=cpu_usage, limit=None)

    def __calculate_memory_proposal(
        self, history_data: MetricsPodData, object_data: K8sObjectData
    ) -> ResourceRecommendation:
        data = history_data["MaxMemoryLoader"]
        info: list[str] = []

        if self.settings.use_oomkill_data:
            max_oomkill_data = history_data["MaxOOMKilledMemoryLoader"]
            max_oomkill_value = (
                np.max([values[0, 1] for values in max_oomkill_data.values()]) if len(max_oomkill_data) > 0 else 0
            )
            if max_oomkill_value != 0:
                info.append("OOMKill detected")
        else:
            max_oomkill_value = 0

        if len(data) == 0:
            return ResourceRecommendation.undefined(info="No data")

        data_count = {pod: values[0, 1] for pod, values in history_data["MemoryAmountLoader"].items()}
        total_points_count = sum(data_count.values())

        if total_points_count < self.settings.points_required:
            return ResourceRecommendation.undefined(info="Not enough data")

        if (
            object_data.hpa is not None
            and object_data.hpa.target_memory_utilization_percentage is not None
            and not self.settings.allow_hpa
        ):
            return ResourceRecommendation.undefined(info="HPA detected")

        memory_usage = self.settings.calculate_memory_proposal(data, max_oomkill_value)
        return ResourceRecommendation(request=memory_usage, limit=memory_usage, info=", ".join(info) if info else None)

    def run(self, history_data: MetricsPodData, object_data: K8sObjectData) -> RunResult:
        return {
            ResourceType.CPU: self.__calculate_cpu_proposal(history_data, object_data),
            ResourceType.Memory: self.__calculate_memory_proposal(history_data, object_data),
        }
