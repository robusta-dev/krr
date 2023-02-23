import pydantic as pd

from robusta_krr.core.formatters import FormatType
from robusta_krr.core.strategies import StrategySettings, BaseStrategy, get_strategy_from_name


class Config(pd.BaseSettings):
    quiet: bool = pd.Field(False)
    verbose: bool = pd.Field(False)

    prometheus_url: str | None = pd.Field(None)
    format: FormatType = pd.Field(FormatType.text)
    strategy: str = pd.Field("simple")
    strategy_settings: StrategySettings = pd.Field(StrategySettings())

    def create_strategy(self) -> BaseStrategy:
        return get_strategy_from_name(self.strategy)(self.strategy_settings)

    @pd.validator("strategy")
    def validate_strategy(cls, v: str) -> str:
        get_strategy_from_name(v)  # raises if strategy is not found
        return v
