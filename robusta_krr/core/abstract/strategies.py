from __future__ import annotations

import abc
import datetime
from typing import Generic, TypeVar

import pydantic as pd

from robusta_krr.core.models.result import K8sObjectData, ResourceType


class ResourceRecommendation(pd.BaseModel):
    request: float
    limit: float


class StrategySettings(pd.BaseModel):
    history_duration: float = pd.Field(
        24 * 7 * 2, ge=1, description="The duration of the history data to use (in hours)."
    )

    @property
    def history_timedelta(self) -> datetime.timedelta:
        return datetime.timedelta(hours=self.history_duration)


_StrategySettings = TypeVar("_StrategySettings", bound=StrategySettings)
HistoryData = dict[str, list[float]]


class BaseStrategy(abc.ABC, Generic[_StrategySettings]):
    __display_name__: str
    settings: _StrategySettings

    def __init__(self, settings: _StrategySettings):
        self.settings = settings

    def __str__(self) -> str:
        return self.__display_name__.title()

    @abc.abstractmethod
    def run(
        self, history_data: HistoryData, object_data: K8sObjectData, resource_type: ResourceType
    ) -> ResourceRecommendation:
        """Run the strategy to calculate the recommendation"""

    @staticmethod
    def find(name: str) -> type[BaseStrategy]:
        """Get a strategy from its name."""

        # NOTE: Load default formatters
        from robusta_krr import strategies as _  # noqa: F401

        strategies = {cls.__display_name__.lower(): cls for cls in BaseStrategy.__subclasses__()}
        if name.lower() in strategies:
            return strategies[name.lower()]

        raise ValueError(f"Unknown strategy name: {name}. Available strategies: {', '.join(strategies)}")


__all__ = [
    "BaseStrategy",
    "StrategySettings",
    "HistoryData",
    "K8sObjectData",
    "ResourceType",
]
