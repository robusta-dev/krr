from typing import Any, Literal, Optional, Union

import pydantic as pd
from kubernetes import config
from kubernetes.config.config_exception import ConfigException
from rich.console import Console

from robusta_krr.core.abstract import formatters
from robusta_krr.core.abstract.strategies import AnyStrategy, BaseStrategy
from robusta_krr.core.models.objects import KindLiteral


class Config(pd.BaseSettings):
    quiet: bool = pd.Field(False)
    verbose: bool = pd.Field(False)

    clusters: Union[list[str], Literal["*"], None] = None
    kubeconfig: Optional[str] = None
    namespaces: Union[list[str], Literal["*"]] = pd.Field("*")
    resources: Union[list[KindLiteral], Literal["*"]] = pd.Field("*")
    selector: Optional[str] = None

    # Value settings
    cpu_min_value: int = pd.Field(10, ge=0)  # in millicores
    memory_min_value: int = pd.Field(100, ge=0)  # in megabytes

    # Prometheus Settings
    prometheus_url: Optional[str] = pd.Field(None)
    prometheus_auth_header: Optional[str] = pd.Field(None)
    prometheus_other_headers: dict[str, str] = pd.Field(default_factory=dict)
    prometheus_ssl_enabled: bool = pd.Field(False)
    prometheus_cluster_label: Optional[str] = pd.Field(None)
    prometheus_label: Optional[str] = pd.Field(None)
    eks_managed_prom: bool = pd.Field(False)
    eks_managed_prom_profile_name: Optional[str] = pd.Field(None)
    eks_access_key: Optional[str] = pd.Field(None)
    eks_secret_key: Optional[str] = pd.Field(None)
    eks_service_name: Optional[str] = pd.Field(None)
    eks_managed_prom_region: Optional[str] = pd.Field(None)
    coralogix_token: Optional[str] = pd.Field(None)

    # Threading settings
    max_workers: int = pd.Field(6, ge=1)

    # Logging Settings
    format: str
    strategy: str
    log_to_stderr: bool

    # Outputs Settings
    file_output: Optional[str] = pd.Field(None)
    slack_output: Optional[str] = pd.Field(None)

    other_args: dict[str, Any]

    # Internal
    inside_cluster: bool = False
    console: Optional[Console] = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.console = Console(stderr=self.log_to_stderr)

    @property
    def Formatter(self) -> formatters.FormatterFunc:
        return formatters.find(self.format)

    @pd.validator("prometheus_other_headers", pre=True)
    def validate_prometheus_other_headers(cls, headers: Union[list[str], dict[str, str]]) -> dict[str, str]:
        if isinstance(headers, dict):
            return headers

        return {k.strip().lower(): v.strip() for k, v in [header.split(":") for header in headers]}

    @pd.validator("namespaces")
    def validate_namespaces(cls, v: Union[list[str], Literal["*"]]) -> Union[list[str], Literal["*"]]:
        if v == []:
            return "*"

        return [val.lower() for val in v]

    @pd.validator("resources", pre=True)
    def validate_resources(cls, v: Union[list[str], Literal["*"]]) -> Union[list[str], Literal["*"]]:
        if v == []:
            return "*"

        return [val.lower() for val in v]

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
        formatters.find(v)  # NOTE: raises if strategy is not found
        return v

    @property
    def context(self) -> Optional[str]:
        return self.clusters[0] if self.clusters != "*" and self.clusters else None

    def load_kubeconfig(self) -> None:
        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config(config_file=self.kubeconfig, context=self.context)
            self.inside_cluster = False
        else:
            self.inside_cluster = True
