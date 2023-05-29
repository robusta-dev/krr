from typing import Any, Literal, Optional, Union

import pydantic as pd
from kubernetes import config
from kubernetes.config.config_exception import ConfigException

from robusta_krr.core.abstract.formatters import BaseFormatter
from robusta_krr.core.abstract.strategies import AnyStrategy, BaseStrategy

try:
    config.load_incluster_config()
except ConfigException:
    try:
        config.load_kube_config()
    except ConfigException:
        IN_CLUSTER = None
    else:
        IN_CLUSTER = False
else:
    IN_CLUSTER = True


class Config(pd.BaseSettings):
    quiet: bool = pd.Field(False)
    verbose: bool = pd.Field(False)

    clusters: Union[list[str], Literal["*"], None] = None
    namespaces: Union[list[str], Literal["*"]] = pd.Field("*")

    # Value settings
    cpu_min_value: int = pd.Field(5, ge=0)  # in millicores
    memory_min_value: int = pd.Field(10, ge=0)  # in megabytes

    # Prometheus Settings
    prometheus_url: Optional[str] = pd.Field(None)
    prometheus_auth_header: Optional[str] = pd.Field(None)
    prometheus_ssl_enabled: bool = pd.Field(False)

    # Logging Settings
    format: str
    strategy: str
    log_to_stderr: bool

    other_args: dict[str, Any]

    @property
    def Formatter(self) -> type[BaseFormatter]:
        return BaseFormatter.find(self.format)

    @pd.validator("namespaces")
    def validate_namespaces(cls, v: Union[list[str], Literal["*"]]) -> Union[list[str], Literal["*"]]:
        if v == []:
            return "*"

        return v

    def create_strategy(self) -> AnyStrategy:
        StrategyType = AnyStrategy.find(self.strategy)
        StrategySettingsType = StrategyType.get_settings_type()
        return StrategyType(StrategySettingsType(**self.other_args))  # type: ignore

    @pd.validator("strategy")
    def validate_strategy(cls, v: str) -> str:
        BaseStrategy.find(v)  # NOTE: raises if strategy is not found
        return v

    @pd.validator("format")
    def validate_format(cls, v: str) -> str:
        BaseFormatter.find(v)  # NOTE: raises if strategy is not found
        return v

    @property
    def config_loaded(self) -> bool:
        return IN_CLUSTER is not None

    @property
    def inside_cluster(self) -> bool:
        return bool(IN_CLUSTER)
