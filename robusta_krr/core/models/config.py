from __future__ import annotations

import logging
import sys
from typing import Any, Literal, Optional, Union

import pydantic as pd
from kubernetes import config
from kubernetes.config.config_exception import ConfigException
from rich.console import Console
from rich.logging import RichHandler

from robusta_krr.core.abstract import formatters
from robusta_krr.core.abstract.strategies import AnyStrategy, BaseStrategy
from robusta_krr.core.models.objects import KindLiteral

logger = logging.getLogger("krr")


class Config(pd.BaseSettings):
    quiet: bool = pd.Field(False)
    verbose: bool = pd.Field(False)

    clusters: Union[list[str], Literal["*"], None] = None
    kubeconfig: Optional[str] = None
    impersonate_user: Optional[str] = None
    impersonate_group: Optional[str] = None
    namespaces: Union[list[str], Literal["*"]] = pd.Field("*")
    resources: Union[list[KindLiteral], Literal["*"]] = pd.Field("*")
    selector: Optional[str] = None

    # Value settings
    cpu_min_value: int = pd.Field(10, ge=0)  # in millicores
    memory_min_value: int = pd.Field(100, ge=0)  # in megabytes

    # Prometheus Settings
    prometheus_url: Optional[str] = pd.Field(None)
    prometheus_auth_header: Optional[pd.SecretStr] = pd.Field(None)
    prometheus_other_headers: dict[str, pd.SecretStr] = pd.Field(default_factory=dict)
    prometheus_ssl_enabled: bool = pd.Field(False)
    prometheus_cluster_label: Optional[str] = pd.Field(None)
    prometheus_label: Optional[str] = pd.Field(None)
    eks_managed_prom: bool = pd.Field(False)
    eks_managed_prom_profile_name: Optional[str] = pd.Field(None)
    eks_access_key: Optional[str] = pd.Field(None)
    eks_secret_key: Optional[pd.SecretStr] = pd.Field(None)
    eks_service_name: Optional[str] = pd.Field(None)
    eks_managed_prom_region: Optional[str] = pd.Field(None)
    coralogix_token: Optional[pd.SecretStr] = pd.Field(None)
    openshift: bool = pd.Field(False)

    # Threading settings
    max_workers: int = pd.Field(6, ge=1)

    # Logging Settings
    format: str
    show_cluster_name: bool
    strategy: str
    log_to_stderr: bool
    width: Optional[int] = pd.Field(None, ge=1)
    show_severity: bool = True

    # Output Settings
    file_output: Optional[str] = pd.Field(None)
    file_output_dynamic: bool = pd.Field(False)
    slack_output: Optional[str] = pd.Field(None)

    other_args: dict[str, Any]

    # Internal
    inside_cluster: bool = False
    _logging_console: Optional[Console] = pd.PrivateAttr(None)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    @property
    def Formatter(self) -> formatters.FormatterFunc:
        return formatters.find(self.format)

    @pd.validator("prometheus_url")
    def validate_prometheus_url(cls, v: Optional[str]):
        if v is None:
            return None

        if not v.startswith("https://") and not v.startswith("http://"):
            raise Exception("--prometheus-url must start with https:// or http://")

        v = v.removesuffix("/")

        return v

    @pd.validator("prometheus_other_headers", pre=True)
    def validate_prometheus_other_headers(cls, headers: Union[list[str], dict[str, str]]) -> dict[str, str]:
        if isinstance(headers, dict):
            return headers

        return {k.strip().lower(): v.strip() for k, v in [header.split(":") for header in headers]}

    @pd.validator("namespaces")
    def validate_namespaces(cls, v: Union[list[str], Literal["*"]]) -> Union[list[str], Literal["*"]]:
        if v == []:
            return "*"

        if isinstance(v, list):
            for val in v:
                if val.startswith("*"):
                    raise ValueError("Namespace's values cannot start with an asterisk (*)")

        return [val.lower() for val in v]

    @pd.validator("resources", pre=True)
    def validate_resources(cls, v: Union[list[str], Literal["*"]]) -> Union[list[str], Literal["*"]]:
        if v == []:
            return "*"

        # NOTE: KindLiteral.__args__ is a tuple of all possible values of KindLiteral
        # So this will preserve the big and small letters of the resource
        return [next(r for r in KindLiteral.__args__ if r.lower() == val.lower()) for val in v]

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

    @property
    def logging_console(self) -> Console:
        if getattr(self, "_logging_console") is None:
            self._logging_console = Console(file=sys.stderr if self.log_to_stderr else sys.stdout, width=self.width)
        return self._logging_console

    def load_kubeconfig(self) -> None:
        try:
            config.load_kube_config(config_file=self.kubeconfig, context=self.context)
            self.inside_cluster = False
        except ConfigException:
            config.load_incluster_config()
            self.inside_cluster = True

    def get_kube_client(self, context: Optional[str] = None):
        if context is None:
            return None

        api_client = config.new_client_from_config(context=context, config_file=self.kubeconfig)
        if self.impersonate_user is not None:
            # trick copied from https://github.com/kubernetes-client/python/issues/362
            api_client.set_default_header("Impersonate-User", self.impersonate_user)
        if self.impersonate_group is not None:
            api_client.set_default_header("Impersonate-Group", self.impersonate_group)
        return api_client

    @staticmethod
    def set_config(config: Config) -> None:
        global _config

        _config = config
        logging.basicConfig(
            level="NOTSET",
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(console=config.logging_console)],
        )
        logging.getLogger("").setLevel(logging.CRITICAL)
        logger.setLevel(logging.DEBUG if config.verbose else logging.CRITICAL if config.quiet else logging.INFO)

    @staticmethod
    def get_config() -> Optional[Config]:
        return _config


# NOTE: This class is just a proxy for _config.
# Import settings from this module and use it like it is just a config object.
class _Settings(Config):  # Config here is used for type checking
    def __init__(self) -> None:
        pass

    def __getattr__(self, name: str):
        if _config is None:
            raise AttributeError("Config is not set")

        return getattr(_config, name)


_config: Optional[Config] = None
settings = _Settings()
