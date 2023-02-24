from typing import get_args

import pydantic as pd

from robusta_krr.core.formatters import BaseFormatter
from robusta_krr.core.strategies import BaseStrategy, StrategySettings


class Config(pd.BaseSettings):
    quiet: bool = pd.Field(False)
    verbose: bool = pd.Field(False)

    prometheus_url: str | None = pd.Field(None)
    format: str
    strategy: str

    def create_strategy(self) -> BaseStrategy:
        StrategyType = BaseStrategy.find(self.strategy)
        StrategySettingsType: type[StrategySettings] = get_args(StrategyType.__orig_bases__[0])[0]  # type: ignore
        return StrategyType(StrategySettingsType())

    @pd.validator("strategy")
    def validate_strategy(cls, v: str) -> str:
        BaseStrategy.find(v)  # NOTE: raises if strategy is not found
        return v

    @pd.validator("format")
    def validate_format(cls, v: str) -> str:
        BaseFormatter.find(v)  # NOTE: raises if strategy is not found
        return v
