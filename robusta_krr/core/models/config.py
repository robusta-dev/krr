from __future__ import annotations

import logging
import sys
from typing import Any, Literal, Optional, Union, List

import pydantic as pd
import typer
from kubernetes import config
from kubernetes.config.config_exception import ConfigException
from pydantic.fields import ModelField
from rich.console import Console
from rich.logging import RichHandler

from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.objects import KindLiteral

logger = logging.getLogger("krr")


class Config(pd.BaseSettings):
    quiet: bool = pd.Field(False)
    verbose: bool = pd.Field(False)

    clusters: Union[list[str], Literal["*"], None] = None
    kubeconfig: Optional[str] = None
    namespaces: Union[list[str], Literal["*"]] = pd.Field("*")
    resources: Union[list[KindLiteral], Literal["*"]] = pd.Field("*")
    selector: Optional[str] = None

    # Value settings
    cpu_min_value: int = pd.Field(10, ge=0, description="Sets the minimum recommended cpu value in millicores.")  # in millicores
    memory_min_value: int = pd.Field(100, ge=0, description="Sets the minimum recommended memory value in MB.")  # in megabytes

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
    format: str
    log_to_stderr: bool
    width: Optional[int] = pd.Field(None, ge=1)

    # Outputs Settings
    file_output: Optional[str] = pd.Field(None)
    slack_output: Optional[str] = pd.Field(None)

    # Internal
    inside_cluster: bool = False
    _logging_console: Optional[Console] = pd.PrivateAttr(None)
    _result_console: Optional[Console] = pd.PrivateAttr(None)

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

        return [val.lower() for val in v]

    @pd.validator("resources", pre=True)
    def validate_resources(cls, v: Union[list[str], Literal["*"]]) -> Union[list[str], Literal["*"]]:
        if v == []:
            return "*"

        return [val.capitalize() for val in v]
    

    @pd.validator("format")
    def validate_format(cls, v: str) -> str:
        formatters.find(v)  # NOTE: raises if formatter is not found
        return v

    @property
    def context(self) -> Optional[str]:
        return self.clusters[0] if self.clusters != "*" and self.clusters else None

    @property
    def logging_console(self) -> Console:
        if getattr(self, "_logging_console") is None:
            self._logging_console = Console(file=sys.stderr if self.log_to_stderr else sys.stdout, width=self.width)
        return self._logging_console

    @property
    def result_console(self) -> Console:
        if getattr(self, "_result_console") is None:
            self._result_console = Console(file=sys.stdout, width=self.width)
        return self._result_console

    def load_kubeconfig(self) -> None:
        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config(config_file=self.kubeconfig, context=self.context)
            self.inside_cluster = False
        else:
            self.inside_cluster = True

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


# NOTE: This class is just a proxy for _config so you can access it globally without passing it around everywhere
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


# Helper for defining command line options
def pydantic_field_to_typer_option(option_names: List[str], rich_help_panel: str, field: ModelField) -> typer.Option:
    """
    Create a typer option from a pydantic field.
    We use this to generate cli options with default values and help text, without repeating ourselves.
    """
    return typer.Option(
        field.default,
        *option_names,
        help=field.field_info.description,
        rich_help_panel=rich_help_panel,
    )

# Common command line options
# For new CLI options, use "--dashes-like-this" and "--not_undersores_like_this"
# For backwards compatibility, some CLI options support both styles  
option_kubeconfig: Optional[str] = typer.Option(
    None,
    "--kubeconfig",
    "-k",
    help="Path to kubeconfig file. If not provided, will attempt to find it.",
    rich_help_panel="Kubernetes Settings",
)
option_clusters: List[str] = typer.Option(
    None,
    "--context",
    "--cluster",
    "-c",
    help="List of clusters to run on. By default, will run on the current cluster. Use --all-clusters to run on all clusters.",
    rich_help_panel="Kubernetes Settings",
)
option_all_clusters: bool = typer.Option(
    False,
    "--all-clusters",
    help="Run on all clusters. Overrides --context.",
    rich_help_panel="Kubernetes Settings",
)
option_namespaces: List[str] = typer.Option(
    None,
    "--namespace",
    "-n",
    help="List of namespaces to run on. By default, will run on all namespaces except 'kube-system'.",
    rich_help_panel="Kubernetes Settings",
)
option_resources: List[str] = typer.Option(
    None,
    "--resource",
    "-r",
    help="List of resources to run on (Deployment, StatefulSet, DaemonSet, Job, Rollout). By default, will run on all resources. Case insensitive.",
    rich_help_panel="Kubernetes Settings",
)
option_selector: Optional[str] = typer.Option(
    None,
    "--selector",
    "-s",
    help="Selector (label query) to filter on, supports '=', '==', and '!='.(e.g. -s key1=value1,key2=value2). Matching objects must satisfy all of the specified label constraints.",
    rich_help_panel="Kubernetes Settings",
)
option_prometheus_url: Optional[str] = typer.Option(
    None,
    "--prometheus-url",
    "-p",
    help="Prometheus URL. If not provided, will attempt to find it in kubernetes cluster",
    rich_help_panel="Prometheus Settings",
)
option_prometheus_auth_header: Optional[str] = typer.Option(
    None,
    "--prometheus-auth-header",
    help="Prometheus authentication header.",
    rich_help_panel="Prometheus Settings",
)
option_prometheus_other_headers: Optional[List[str]] = typer.Option(
    None,
    "--prometheus-headers",
    "-H",
    help="Additional headers to add to Prometheus requests. Format as 'key: value', for example 'X-MyHeader: 123'. Trailing whitespaces will be stripped.",
    rich_help_panel="Prometheus Settings",
)
option_prometheus_ssl_enabled: bool = typer.Option(
    False,
    "--prometheus-ssl-enabled",
    help="Enable SSL for Prometheus requests.",
    rich_help_panel="Prometheus Settings",
)
option_prometheus_cluster_label: Optional[str] = typer.Option(
    None,
    "--prometheus-cluster-label",
    "-l",
    help="The label in prometheus for your cluster.(Only relevant for centralized prometheus)",
    rich_help_panel="Prometheus Settings",
)
option_prometheus_label: str = typer.Option(
    None,
    "--prometheus-label",
    help="The label in prometheus used to differentiate clusters. (Only relevant for centralized prometheus)",
    rich_help_panel="Prometheus Settings",
)
option_eks_managed_prom: bool = typer.Option(
    False,
    "--eks-managed-prom",
    help="Adds additional signitures for eks prometheus connection.",
    rich_help_panel="Prometheus EKS Settings",
)
option_eks_managed_prom_profile_name: Optional[str] = typer.Option(
    None,
    "--eks-profile-name",
    help="Sets the profile name for eks prometheus connection.",
    rich_help_panel="Prometheus EKS Settings",
)
option_eks_access_key: Optional[str] = typer.Option(
    None,
    "--eks-access-key",
    help="Sets the access key for eks prometheus connection.",
    rich_help_panel="Prometheus EKS Settings",
)
option_eks_secret_key: Optional[str] = typer.Option(
    None,
    "--eks-secret-key",
    help="Sets the secret key for eks prometheus connection.",
    rich_help_panel="Prometheus EKS Settings",
)
option_eks_service_name: Optional[str] = typer.Option(
    "aps",
    "--eks-service-name",
    help="Sets the service name for eks prometheus connection.",
    rich_help_panel="Prometheus EKS Settings",
)
option_eks_managed_prom_region: Optional[str] = typer.Option(
    None,
    "--eks-managed-prom-region",
    help="Sets the region for eks prometheus connection.",
    rich_help_panel="Prometheus EKS Settings",
)
option_coralogix_token: Optional[str] = typer.Option(
    None,
    "--coralogix-token",
    help="Adds the token needed to query Coralogix managed prometheus.",
    rich_help_panel="Prometheus Coralogix Settings",
)
option_openshift: bool = typer.Option(
    False,
    "--openshift",
    help="Used when running by Robusta inside an OpenShift cluster.",
    rich_help_panel="Prometheus Openshift Settings",
    hidden=True,
)
option_max_workers: int = typer.Option(
    10,
    "--max-workers",
    "-w",
    help="Max workers to use for async requests.",
    rich_help_panel="Threading Settings",
)
option_format: str = typer.Option(
    "table",
    "--formatter",
    "-f",
    help=f"Output formatter ({', '.join(formatters.list_available())})",
    rich_help_panel="Logging Settings",
)
option_verbose: bool = typer.Option(
    False, "--verbose", "-v", help="Enable verbose mode", rich_help_panel="Logging Settings"
)
option_quiet: bool = typer.Option(
    False, "--quiet", "-q", help="Enable quiet mode", rich_help_panel="Logging Settings"
)
option_log_to_stderr: bool = typer.Option(
    False, "--logtostderr", help="Pass logs to stderr", rich_help_panel="Logging Settings"
)
option_width: Optional[int] = typer.Option(
    None,
    "--width",
    help="Width of the output. Will use console width by default.",
    rich_help_panel="Logging Settings",
)
option_file_output: Optional[str] = typer.Option(
    None, "--fileoutput", help="Print the output to a file", rich_help_panel="Output Settings"
)
option_slack_output: Optional[str] = typer.Option(
    None,
    "--slackoutput",
    help="Send to output to a slack channel, must have SLACK_BOT_TOKEN",
    rich_help_panel="Output Settings",
)
option_cpu_min_value: int = pydantic_field_to_typer_option(
    ["--cpu-min", "--cpu_min"],
    "Strategy Settings",
    Config.__fields__["cpu_min_value"]
)
option_memory_min_value: int = pydantic_field_to_typer_option(
    ["--mem-min", "--mem_min"],
    "Strategy Settings",
    Config.__fields__["memory_min_value"]
)