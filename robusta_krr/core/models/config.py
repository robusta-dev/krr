import pydantic as pd

from typing import Literal

from robusta_krr.core.abstract.formatters import BaseFormatter
from robusta_krr.core.abstract.strategies import AnyStrategy, BaseStrategy


class Config(pd.BaseSettings):
    quiet: bool = pd.Field(False)
    verbose: bool = pd.Field(False)

    clusters: list[str] | Literal["*"] | None = None
    namespaces: list[str] | Literal["*"] = pd.Field("*")

    # Make this True if you are running KRR inside the cluster
    inside_cluster: bool = pd.Field(False)

    # Prometheus Settings
    prometheus_url: str | None = pd.Field(None)
    prometheus_auth_header: str | None = pd.Field(None)
    prometheus_ssl_enabled: bool = pd.Field(False)

    format: str
    strategy: str

    other_args: list[str] = pd.Field([])

    def _parse_other_args(self) -> dict[str, str]:
        args = {}
        for arg in self.other_args:
            if "=" not in arg and not arg.startswith("--"):
                continue

            key, value = arg.split("=")
            args[key[2:]] = value

        return args

    def create_strategy(self) -> BaseStrategy:
        StrategyType = AnyStrategy.find(self.strategy)
        StrategySettingsType = StrategyType.get_settings_type()
        return StrategyType(StrategySettingsType(**self._parse_other_args()))

    @pd.validator("strategy")
    def validate_strategy(cls, v: str) -> str:
        BaseStrategy.find(v)  # NOTE: raises if strategy is not found
        return v

    @pd.validator("format")
    def validate_format(cls, v: str) -> str:
        BaseFormatter.find(v)  # NOTE: raises if strategy is not found
        return v
