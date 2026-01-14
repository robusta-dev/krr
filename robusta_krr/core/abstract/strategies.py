from __future__ import annotations

import abc
import datetime
import enum
from typing import TYPE_CHECKING, Optional

import pydantic

from robusta_krr.core.models.allocations import NONE_LITERAL, RecommendationValue, ResourceAllocations
from robusta_krr.core.models.result import ResourceType

if TYPE_CHECKING:
    from robusta_krr.core.models.config import Settings


class HistoryData(pydantic.BaseModel):
    data: list[list]


class MetricsPodData(pydantic.BaseModel):
    name: str
    deleted: bool
    metrics: dict[ResourceType, HistoryData]


class RunResult(pydantic.BaseModel):
    scan: dict[str, RecommendationValue]
    object_: "K8sObjectData"


class PodsTimeData(pydantic.BaseModel):
    pod_count: int
    first_sample_time: Optional[datetime.datetime]


class StrategySettings(pydantic.BaseModel):
    pass


class ResourceHistoryData(pydantic.BaseModel):
    """Historical data for a single resource type."""

    data: list[list]


class HistoryRange(enum.Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class BaseStrategy(abc.ABC):
    """
    A Strategy is a class that defines the logic for calculating the recommendations.

    It should be inherited and implement the abstract methods.
    It can then be registered with the `@strategy` decorator.
    """

    display_name: str = "Base Strategy"
    rich_console: bool = False
    metrics: list
    settings: StrategySettings

    @classmethod
    @abc.abstractmethod
    def find_runs(
        cls, history_data: dict[str, MetricsPodData], object_: "K8sObjectData"
    ) -> list[RunResult]:
        """
        Find the runs of the pods in the history data.
        """
        ...

    @classmethod
    @abc.abstractmethod
    def run(
        cls, history_data: dict[str, MetricsPodData], object_data: "K8sObjectData"
    ) -> ResourceAllocations:
        """
        Run the strategy on the history data and return the result.
        """
        ...

    @classmethod
    def get_query_time_range(
        cls, settings: "Settings", range: HistoryRange = HistoryRange.MEDIUM
    ) -> tuple[datetime.datetime, datetime.datetime]:
        """
        Get the time range for the metrics query.

        If settings.start_time and settings.end_time are both provided,
        use them directly (absolute timeframe mode).

        Otherwise, calculate from history_duration relative to current time
        (relative timeframe mode).
        """
        # Check for absolute timeframe mode
        if settings.start_time is not None and settings.end_time is not None:
            return settings.start_time, settings.end_time

        # Relative timeframe mode (original behavior)
        now = datetime.datetime.now()
        match range:
            case HistoryRange.SHORT:
                duration = datetime.timedelta(hours=settings.timeframe_duration)
            case HistoryRange.MEDIUM:
                duration = datetime.timedelta(hours=settings.history_duration)
            case HistoryRange.LONG:
                duration = datetime.timedelta(
                    hours=min(settings.history_duration * 2, 30 * 24)
                )

        return now - duration, now


class K8sObjectData(pydantic.BaseModel):
    """
    A Kubernetes object data.
    """

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    cluster: Optional[str]
    name: str
    container: str
    pods: list[str]
    hpa: Optional["HPAData"]
    namespace: str
    kind: str
    allocations: ResourceAllocations
    labels: dict[str, str] = pydantic.Field(default_factory=dict)
    current_pods_count: int = 0


class HPAData(pydantic.BaseModel):
    """
    HPA data.
    """

    min_replicas: Optional[int]
    max_replicas: int
    current_replicas: Optional[int]
    desired_replicas: Optional[int]
    target_cpu_utilization_percentage: Optional[float]
    target_memory_utilization_percentage: Optional[float]
