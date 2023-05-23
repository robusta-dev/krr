from __future__ import annotations

import abc
import datetime
import numpy as np
from numpy.typing import NDArray
from typing import Generic, Optional, TypeVar, get_args, Annotated, Literal
from textwrap import dedent

import pydantic as pd

from robusta_krr.core.models.result import K8sObjectData, ResourceType, Metric
from robusta_krr.utils.display_name import add_display_name


SelfRR = TypeVar("SelfRR", bound="ResourceRecommendation")


class ResourceRecommendation(pd.BaseModel):
    request: Optional[float]
    limit: Optional[float]

    @classmethod
    def undefined(cls: type[SelfRR]) -> SelfRR:
        return cls(request=float('NaN'), limit=float('NaN'))


class StrategySettings(pd.BaseModel):
    history_duration: float = pd.Field(
        24 * 7 * 2, ge=1, description="The duration of the history data to use (in hours)."
    )
    timeframe_duration: float = pd.Field(15, ge=1, description="The step for the history data (in minutes).")

    @property
    def history_timedelta(self) -> datetime.timedelta:
        return datetime.timedelta(hours=self.history_duration)

    @property
    def timeframe_timedelta(self) -> datetime.timedelta:
        return datetime.timedelta(minutes=self.timeframe_duration)


_StrategySettings = TypeVar("_StrategySettings", bound=StrategySettings)

ArrayNx2 = Annotated[NDArray[np.float64], Literal["N", 2]]


class ResourceHistoryData(pd.BaseModel):
    metric: Metric
    data: dict[str, ArrayNx2]  # Mapping: pod -> (time, value)

    class Config:
        arbitrary_types_allowed = True


HistoryData = dict[ResourceType, ResourceHistoryData]
RunResult = dict[ResourceType, ResourceRecommendation]

SelfBS = TypeVar("SelfBS", bound="BaseStrategy")


@add_display_name(postfix="Strategy")
class BaseStrategy(abc.ABC, Generic[_StrategySettings]):
    __display_name__: str

    settings: _StrategySettings

    def __init__(self, settings: _StrategySettings):
        self.settings = settings

    def __str__(self) -> str:
        return self.__display_name__.title()

    @property
    def description(self) -> Optional[str]:
        """
            Generate a description for the strategy.
            You can use the settings in the description by using the format syntax.
            Also you can use Rich's markdown syntax to format the description.
        """

        if self.__doc__ is None:
            return None

        return f"[b]{self} Strategy[/b]\n\n" + dedent(self.__doc__.format_map(self.settings.dict())).strip()

    @abc.abstractmethod
    def run(self, history_data: HistoryData, object_data: K8sObjectData) -> RunResult:
        """Run the strategy to calculate the recommendation"""

    @classmethod
    def find(cls: type[SelfBS], name: str) -> type[SelfBS]:
        """Get a strategy from its name."""

        strategies = cls.get_all()
        if name.lower() in strategies:
            return strategies[name.lower()]

        raise ValueError(f"Unknown strategy name: {name}. Available strategies: {', '.join(strategies)}")

    @classmethod
    def get_all(cls: type[SelfBS]) -> dict[str, type[SelfBS]]:
        # NOTE: Load default formatters
        from robusta_krr import strategies as _  # noqa: F401

        return {sub_cls.__display_name__.lower(): sub_cls for sub_cls in cls.__subclasses__()}

    @classmethod
    def get_settings_type(cls) -> type[StrategySettings]:
        return get_args(cls.__orig_bases__[0])[0]  # type: ignore


AnyStrategy = BaseStrategy[StrategySettings]

__all__ = [
    "AnyStrategy",
    "BaseStrategy",
    "StrategySettings",
    "HistoryData",
    "K8sObjectData",
    "ResourceType",
]
