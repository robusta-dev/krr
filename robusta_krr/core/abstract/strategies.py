from __future__ import annotations

import abc
import datetime
from textwrap import dedent
from typing import TYPE_CHECKING, Annotated, Generic, Literal, Optional, Sequence, TypeVar, get_args

import numpy as np
import pydantic as pd
from numpy.typing import NDArray

from robusta_krr.core.models.result import K8sObjectData, ResourceType

if TYPE_CHECKING:
    from robusta_krr.core.abstract.metrics import BaseMetric  # noqa: F401
    from robusta_krr.core.integrations.prometheus.metrics import PrometheusMetric

SelfRR = TypeVar("SelfRR", bound="ResourceRecommendation")


class ResourceRecommendation(pd.BaseModel):
    """A class to represent resource recommendation with optional request and limit values.

    The NaN values are used to represent undefined values: the strategy did not provide a recommendation for the resource.
    None values are used to represent the strategy says that value should not be set.
    """

    request: Optional[float]
    limit: Optional[float]
    info: Optional[str] = pd.Field(
        None, description="Additional information about the recommendation."
    )

    @classmethod
    def undefined(cls: type[SelfRR], info: Optional[str] = None) -> SelfRR:
        return cls(request=float("NaN"), limit=float("NaN"), info=info)


class StrategySettings(pd.BaseModel):
    """A class to represent strategy settings with configurable history and timeframe duration.

    It is used in CLI to generate the help, parameters and validate values.
    Description is used to generate the help.
    Other pydantic features can be used to validate the values.

    Nested classes are not supported here.
    """

    history_duration: float = pd.Field(
        24 * 7 * 2, ge=1, description="The duration of the history data to use (in hours)."
    )
    timeframe_duration: float = pd.Field(1.25, gt=0, description="The step for the history data (in minutes).")

    @property
    def history_timedelta(self) -> datetime.timedelta:
        return datetime.timedelta(hours=self.history_duration)

    @property
    def timeframe_timedelta(self) -> datetime.timedelta:
        return datetime.timedelta(minutes=self.timeframe_duration)

    def history_range_enough(self, history_range: tuple[datetime.timedelta, datetime.timedelta]) -> bool:
        """Override this function to check if the history range is enough for the strategy."""

        return True


# A type alias for a numpy array of shape (N, 2).
ArrayNx2 = Annotated[NDArray[np.float64], Literal["N", 2]]


PodsTimeData = dict[str, ArrayNx2]  # Mapping: pod -> [(time, value)]
MetricsPodData = dict[str, PodsTimeData]

RunResult = dict[ResourceType, ResourceRecommendation]

SelfBS = TypeVar("SelfBS", bound="BaseStrategy")
_StrategySettings = TypeVar("_StrategySettings", bound=StrategySettings)


# An abstract base class for strategy implementation.
# This class requires implementation of a 'run' method for calculating recommendation.
# Make a subclass if you want to create a concrete strategy.
class BaseStrategy(abc.ABC, Generic[_StrategySettings]):
    """An abstract base class for strategy implementation.

    This class is generic, and requires a type for the settings.
    This settings type will be used for the settings property of the strategy.
    It will be used to generate CLI parameters for this strategy, validated by pydantic.

    This class requires implementation of a 'run' method for calculating recommendation.
    Additionally, it provides a 'description' property for generating a description for the strategy.
    Description property uses the docstring of the strategy class and the settings of the strategy.

    The name of the strategy is the name of the class in lowercase, without the 'Strategy' suffix, if exists.
    If you want to change the name of the strategy, you can change the display_name class attribute.

    The strategy will automatically be registered in the strategy registry using __subclasses__ mechanism.
    """

    display_name: str
    rich_console: bool = False

    # TODO: this should be BaseMetric, but currently we only support Prometheus
    @property
    @abc.abstractmethod
    def metrics(self) -> Sequence[type[PrometheusMetric]]:
        pass

    def __init__(self, settings: _StrategySettings):
        self.settings = settings

    def __str__(self) -> str:
        return self.display_name.title()

    @property
    def description(self) -> Optional[str]:
        """
        Generate a description for the strategy.
        You can use Rich's markdown syntax to format the description.
        """
        raise NotImplementedError()

    # Abstract method that needs to be implemented by subclass.
    # This method is intended to calculate resource recommendation based on history data and kubernetes object data.
    @abc.abstractmethod
    def run(self, history_data: MetricsPodData, object_data: K8sObjectData) -> RunResult:
        pass

    # This method is intended to return a strategy by its name.
    @classmethod
    def find(cls: type[SelfBS], name: str) -> type[SelfBS]:
        strategies = cls.get_all()
        if name.lower() in strategies:
            return strategies[name.lower()]

        raise ValueError(f"Unknown strategy name: {name}. Available strategies: {', '.join(strategies)}")

    # This method is intended to return all the available strategies.
    @classmethod
    def get_all(cls: type[SelfBS]) -> dict[str, type[SelfBS]]:
        from robusta_krr import strategies as _  # noqa: F401

        return {sub_cls.display_name.lower(): sub_cls for sub_cls in cls.__subclasses__()}

    # This method is intended to return the type of settings used in strategy.
    @classmethod
    def get_settings_type(cls) -> type[StrategySettings]:
        return get_args(cls.__orig_bases__[0])[0]  # type: ignore


AnyStrategy = BaseStrategy[StrategySettings]


__all__ = [
    "AnyStrategy",
    "BaseStrategy",
    "StrategySettings",
    "PodsTimeData",
    "MetricsPodData",
    "K8sObjectData",
    "ResourceType",
]
