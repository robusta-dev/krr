import textwrap
from datetime import timedelta

import numpy as np
import pydantic as pd

from robusta_krr.core.abstract.strategies import (
    BaseStrategy,
    K8sObjectData,
    MetricsPodData,
    ResourceRecommendation,
    ResourceType,
    RunResult,
    StrategySettings,
)
from robusta_krr.core.integrations.prometheus.metrics import (
    CPUAmountLoader,
    MaxOOMKilledMemoryLoader,
    MemoryAmountLoader,
    PercentileCPULoader,
    PercentileMemoryLoader,
    PrometheusMetric,
)


def _named_loader(factory_fn, name: str, percentile: float) -> type[PrometheusMetric]:
    cls = factory_fn(percentile)
    cls.__name__ = name
    cls.__qualname__ = name
    return cls


class BurstableStrategySettings(StrategySettings):
    cpu_requests_percentile: float = pd.Field(
        50, gt=0, le=100, description="The percentile to use for the CPU request recommendation."
    )
    cpu_limits_percentile: float = pd.Field(
        99, gt=0, le=100, description="The percentile to use for the CPU limit recommendation."
    )
    memory_requests_percentile: float = pd.Field(
        50, gt=0, le=100, description="The percentile to use for the memory request recommendation."
    )
    memory_limits_percentile: float = pd.Field(
        90, gt=0, le=100, description="The percentile to use for the memory limit recommendation."
    )
    memory_buffer_percentage: float = pd.Field(
        15, gt=0, description="The percentage of added buffer on top of the memory limit percentile."
    )
    disable_cpu_limit: bool = pd.Field(
        False, description="When set, CPU limit is left unset (Burstable QoS for CPU)."
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
        description="Whether to bump the memory limit when OOMKills are detected (experimental).",
    )
    oom_memory_buffer_percentage: float = pd.Field(
        25, ge=0, description="What percentage to increase the memory limit when there are OOMKill events."
    )

    def history_range_enough(self, history_range: tuple[timedelta, timedelta]) -> bool:
        start, end = history_range
        return (end - start) >= timedelta(hours=3)


class BurstableStrategy(BaseStrategy[BurstableStrategySettings]):

    display_name = "burstable"
    rich_console = True

    @property
    def metrics(self) -> list[type[PrometheusMetric]]:
        metrics = [
            _named_loader(PercentileCPULoader,    "BurstableCPURequestLoader",    self.settings.cpu_requests_percentile),
            _named_loader(PercentileCPULoader,    "BurstableCPULimitLoader",      self.settings.cpu_limits_percentile),
            _named_loader(PercentileMemoryLoader, "BurstableMemoryRequestLoader", self.settings.memory_requests_percentile),
            _named_loader(PercentileMemoryLoader, "BurstableMemoryLimitLoader",   self.settings.memory_limits_percentile),
            CPUAmountLoader,
            MemoryAmountLoader,
        ]

        if self.settings.use_oomkill_data:
            metrics.append(MaxOOMKilledMemoryLoader)

        return metrics

    @property
    def description(self):
        cpu_limit_desc = "unset" if self.settings.disable_cpu_limit else f"{self.settings.cpu_limits_percentile}% percentile"
        s = textwrap.dedent(f"""\
            CPU request: {self.settings.cpu_requests_percentile}% percentile, limit: {cpu_limit_desc}
            Memory request: {self.settings.memory_requests_percentile}% percentile, limit: {self.settings.memory_limits_percentile}% percentile + {self.settings.memory_buffer_percentage}% buffer
            History: {self.settings.history_duration} hours
            Step: {self.settings.timeframe_duration} minutes

            All parameters can be customized. For example: `krr burstable --cpu-requests-percentile=50 --cpu-limits-percentile=99 --memory-requests-percentile=50 --memory-limits-percentile=90 --memory-buffer-percentage=15`
            """)

        if not self.settings.allow_hpa:
            s += "\n" + textwrap.dedent("""\
                This strategy does not work with objects with HPA defined (Horizontal Pod Autoscaler).
                If HPA is defined for CPU or Memory, the strategy will return "?" for that resource.
                You can override this behaviour by passing the --allow-hpa flag
                """)

        s += "\nLearn more: [underline]https://github.com/robusta-dev/krr#algorithm[/underline]"
        return s

    def __calculate_cpu_proposal(
        self, history_data: MetricsPodData, object_data: K8sObjectData
    ) -> ResourceRecommendation:
        data_req = history_data["BurstableCPURequestLoader"]

        if len(data_req) == 0:
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

        cpu_request = np.max([v[0, 1] for v in data_req.values()])
        cpu_limit = (
            None
            if self.settings.disable_cpu_limit
            else np.max([v[0, 1] for v in history_data["BurstableCPULimitLoader"].values()])
        )
        return ResourceRecommendation(request=cpu_request, limit=cpu_limit)

    def __calculate_memory_proposal(
        self, history_data: MetricsPodData, object_data: K8sObjectData
    ) -> ResourceRecommendation:
        data_req = history_data["BurstableMemoryRequestLoader"]

        oomkill_detected = False

        if self.settings.use_oomkill_data:
            max_oomkill_data = history_data["MaxOOMKilledMemoryLoader"]
            max_oomkill_value = (
                np.max([values[0, 1] for values in max_oomkill_data.values()]) if len(max_oomkill_data) > 0 else 0
            )
            if max_oomkill_value != 0:
                oomkill_detected = True
        else:
            max_oomkill_value = 0

        if len(data_req) == 0:
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

        memory_request = np.max([v[0, 1] for v in data_req.values()])
        memory_limit_base = np.max([v[0, 1] for v in history_data["BurstableMemoryLimitLoader"].values()])
        memory_limit = max(
            memory_limit_base * (1 + self.settings.memory_buffer_percentage / 100),
            max_oomkill_value * (1 + self.settings.oom_memory_buffer_percentage / 100),
        )
        return ResourceRecommendation(
            request=memory_request, limit=memory_limit, info="OOMKill detected" if oomkill_detected else None
        )

    def run(self, history_data: MetricsPodData, object_data: K8sObjectData) -> RunResult:
        return {
            ResourceType.CPU: self.__calculate_cpu_proposal(history_data, object_data),
            ResourceType.Memory: self.__calculate_memory_proposal(history_data, object_data),
        }
