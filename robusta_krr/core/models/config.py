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
from robusta_krr.core.models.objects import KindLiteral

logger = logging.getLogger("krr")


class Config(pd.BaseModel, extra=pd.Extra.ignore):
    kubeconfig: Optional[str] = pd.Field(
        None,
        typer__param_decls=["--kubeconfig", "-k"],
        typer__help="Path to kubeconfig file. If not provided, will attempt to find it.",
        typer__rich_help_panel="Kubernetes Settings",
    )
    impersonate_user: Optional[str] = pd.Field(
        None,
        typer__param_decls=["--as"],
        typer__help="Impersonate a user, just like `kubectl --as`. For example, system:serviceaccount:default:krr-account.",
        typer__rich_help_panel="Kubernetes Settings",
    )
    impersonate_group: Optional[str] = pd.Field(
        None,
        typer__param_decls=["--as-group"],
        typer__help="Impersonate a user inside of a group, just like `kubectl --as-group`. For example, system:authenticated.",
        typer__rich_help_panel="Kubernetes Settings",
    )
    clusters: Union[list[str], Literal["*"], None] = pd.Field(
        None,
        typer__param_decls=["--context", "--cluster", "-c"],
        typer__help=(
            "List of clusters to run on. By default, will run on the current cluster. "
            "Use --all-clusters to run on all clusters."
        ),
        typer__rich_help_panel="Kubernetes Settings",
    )
    all_clusters: bool = pd.Field(
        False,
        typer__param_decls=["--all-clusters"],
        typer__help=("Run on all clusters. Overrides --context."),
        typer__rich_help_panel="Kubernetes Settings",
    )
    namespaces: Union[list[str], Literal["*"]] = pd.Field(
        "*",
        typer__param_decls=["--namespace", "-n"],
        typer__help=("List of namespaces to run on. By default, will run on all namespaces except 'kube-system'."),
        typer__rich_help_panel="Kubernetes Settings",
    )
    resources: Union[list[KindLiteral], Literal["*"]] = pd.Field(
        "*",
        typer__param_decls=["--resource", "-r"],
        typer__help=(
            "List of resources to run on (Deployment, StatefulSet, DaemonSet, Job, Rollout). "
            "By default, will run on all resources. Case insensitive."
        ),
        typer__rich_help_panel="Kubernetes Settings",
    )
    selector: Optional[str] = pd.Field(
        None,
        typer__param_decls=["--context", "--cluster", "-c"],
        typer__help=(
            "List of clusters to run on. By default, will run on the current cluster. "
            "Use --all-clusters to run on all clusters."
        ),
        typer__rich_help_panel="Kubernetes Settings",
    )

    # TODO: Other ones

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
    openshift: bool = pd.Field(False)

    # Threading settings
    max_workers: int = pd.Field(6, ge=1)

    # Logging Settings
    format: str = pd.Field("table")
    show_cluster_name: bool = pd.Field(False)
    log_to_stderr: bool = pd.Field(False)
    width: Optional[int] = pd.Field(None, ge=1)
    quiet: bool = pd.Field(False)
    verbose: bool = pd.Field(False)

    # Outputs Settings
    file_output: Optional[str] = pd.Field(None)
    slack_output: Optional[str] = pd.Field(None)

    # Internal
    inside_cluster: bool = False
    _logging_console: Optional[Console] = pd.PrivateAttr(None)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    @property
    def Formatter(self) -> formatters.FormatterFunc:
        return formatters.find(self.format)

    # @pd.validator("prometheus_url")
    # def validate_prometheus_url(cls, v: Optional[str]):
    #     if v is None:
    #         return None

    #     if not v.startswith("https://") and not v.startswith("http://"):
    #         raise Exception("--prometheus-url must start with https:// or http://")

    #     v = v.removesuffix("/")

    #     return v

    @pd.validator("prometheus_other_headers", pre=True)
    def validate_prometheus_other_headers(cls, headers: Union[list[str], dict[str, str]]) -> dict[str, str]:
        if headers is None:
            return {}

        if isinstance(headers, dict):
            return headers

        return {k.strip().lower(): v.strip() for k, v in [header.split(":") for header in headers]}

    @pd.validator("namespaces")
    def validate_namespaces(cls, v: Union[list[str], Literal["*"]]) -> Union[list[str], Literal["*"]]:
        if v == []:
            return "*"

        return [val.lower() for val in v]

    # @pd.validator("resources", pre=True)
    # def validate_resources(cls, v: Union[list[str], Literal["*"]]) -> Union[list[str], Literal["*"]]:
    #     if v == []:
    #         return "*"

    #     # NOTE: KindLiteral.__args__ is a tuple of all possible values of KindLiteral
    #     # So this will preserve the big and small letters of the resource
    #     return [next(r for r in KindLiteral.__args__ if r.lower() == val.lower()) for val in v]

    # @pd.validator("format")
    # def validate_format(cls, v: str) -> str:
    #     formatters.find(v)  # NOTE: raises if formatter is not found
    #     return v

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
