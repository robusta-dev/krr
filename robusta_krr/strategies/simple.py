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
    MaxMemoryLoader,
    CPULoader,
    PrometheusMetric,
    PercentileCPULoader,
    MaxCPULoader,
    MemoryLoader,
    PercentileMemoryLoader,
)

import matplotlib.pyplot as plt


class SimpleStrategySettings(StrategySettings):
    cpu_percentile: float = pd.Field(99, gt=0, le=100, description="The percentile to use for the CPU recommendation.")
    memory_buffer_percentage: float = pd.Field(
        5, gt=0, description="The percentage of added buffer to the peak memory usage for memory recommendation."
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

        # print("-----")
        # print(data)
        # print(data_)

        return np.max(data_)


from threading import Lock

lock = Lock()


class SimpleStrategy(BaseStrategy[SimpleStrategySettings]):
    """
    CPU request: {cpu_percentile}% percentile, limit: unset
    Memory request: max + {memory_buffer_percentage}%, limit: max + {memory_buffer_percentage}%

    This strategy does not work with objects with HPA defined (Horizontal Pod Autoscaler).
    If HPA is defined for CPU or Memory, the strategy will return "?" for that resource.

    Learn more: [underline]https://github.com/robusta-dev/krr#algorithm[/underline]
    """

    display_name = "simple"
    rich_console = True

    @property
    def metrics(self) -> list[type[PrometheusMetric]]:
        return [
            PercentileCPULoader(self.settings.cpu_percentile),
            CPULoader,
            MaxCPULoader,
            MaxMemoryLoader,
            MemoryLoader,
        ]

    def __calculate_cpu_proposal(
        self, history_data: MetricsPodData, object_data: K8sObjectData
    ) -> ResourceRecommendation:
        data_full = history_data["CPULoader"]
        data_max = history_data["MaxCPULoader"]
        data = history_data["PercentileCPULoader"]

        if len(data) == 0:
            return ResourceRecommendation.undefined(info="No data")

        if object_data.hpa is not None and object_data.hpa.target_cpu_utilization_percentage is not None:
            return ResourceRecommendation.undefined(info="HPA detected")

        cpu_percentile = self.settings.calculate_cpu_proposal(data)
        cpu_max = self.settings.calculate_cpu_proposal(data_max)
        cpu_total = self.settings.calculate_cpu_proposal(data_full)

        with lock:
            plt.rcParams["figure.figsize"] = (20, 20)
            for pod, values in data_full.items():
                plt.plot(values[:, 0], values[:, 1], label=pod)

            plt.xlabel("Time")
            plt.ylabel("CPU usage")
            plt.axhline(cpu_percentile, color="red", label="PercentileCPULoader")
            plt.axhline(cpu_max, color="green", label="MaxCPULoader")
            plt.axhline(cpu_total, color="blue", label="CPULoader")

            plt.legend()
            import uuid

            plt.savefig(f"./test_images/{uuid.uuid4()}.png")
            plt.clf()

        return ResourceRecommendation(request=cpu_percentile, limit=None)

    def __calculate_memory_proposal(
        self, history_data: MetricsPodData, object_data: K8sObjectData
    ) -> ResourceRecommendation:
        data = history_data["MaxMemoryLoader"]
        data_full = history_data["MemoryLoader"]

        if len(data) == 0:
            return ResourceRecommendation.undefined(info="No data")

        if object_data.hpa is not None and object_data.hpa.target_memory_utilization_percentage is not None:
            return ResourceRecommendation.undefined(info="HPA detected")

        memory_usage = self.settings.calculate_memory_proposal(data)

        with lock:
            plt.rcParams["figure.figsize"] = (20, 20)
            for pod, values in data_full.items():
                plt.plot(values[:, 0], values[:, 1], label=pod)

            plt.xlabel("Time")
            plt.ylabel("Memory usage")
            plt.axhline(memory_usage, color="red", label="MaxMemoryLoader")
            # plt.axhline(cpu_max, color="green", label="MaxCPULoader")
            # plt.axhline(cpu_total, color="blue", label="CPULoader")

            plt.legend()
            import uuid

            plt.savefig(f"./test_images/{uuid.uuid4()}.png")
            plt.clf()

        return ResourceRecommendation(request=memory_usage, limit=memory_usage)

    def run(self, history_data: MetricsPodData, object_data: K8sObjectData) -> RunResult:
        return {
            ResourceType.CPU: self.__calculate_cpu_proposal(history_data, object_data),
            ResourceType.Memory: self.__calculate_memory_proposal(history_data, object_data),
        }
