from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import typer
import urllib3
from pydantic import ValidationError  # noqa: F401
from pydantic.fields import ModelField

from robusta_krr import formatters as concrete_formatters  # noqa: F401
from robusta_krr.core.abstract import formatters
from robusta_krr.core.abstract.strategies import StrategySettings
from robusta_krr.strategies.simple import SimpleStrategy, SimpleStrategySettings
from robusta_krr.core.models.config import Config
from robusta_krr.core.runner import Runner
from robusta_krr.utils.version import get_version

app = typer.Typer(pretty_exceptions_show_locals=False, pretty_exceptions_short=True, no_args_is_help=True)

# NOTE: Disable insecure request warnings, as it might be expected to use self-signed certificates inside the cluster
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("krr")


def __pydantic_field_to_typer_option(option_names: List[str], rich_help_panel: str, field: ModelField) -> typer.Option:
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


@app.command(rich_help_panel="Utils")
def version() -> None:
    typer.echo(get_version())


@app.command(name="simple", rich_help_panel="Strategies")
def run_simple(
    # For new CLI options, use "--dashes-like-this" and "--not_undersores_like_this"
    # For backwards compatibility, some CLI options support both styles
    kubeconfig: Optional[str] = typer.Option(
        None,
        "--kubeconfig",
        "-k",
        help="Path to kubeconfig file. If not provided, will attempt to find it.",
        rich_help_panel="Kubernetes Settings",
    ),
    impersonate_user: Optional[str] = typer.Option(
        None,
        "--as",
        help="Impersonate a user, just like `kubectl --as`. For example, system:serviceaccount:default:krr-account.",
        rich_help_panel="Kubernetes Settings",
    ),
        impersonate_group: Optional[str] = typer.Option(
        None,
        "--as-group",
        help="Impersonate a user inside of a group, just like `kubectl --as-group`. For example, system:authenticated.",
        rich_help_panel="Kubernetes Settings",
    ),
    clusters: List[str] = typer.Option(
        None,
        "--context",
        "--cluster",
        "-c",
        help="List of clusters to run on. By default, will run on the current cluster. Use --all-clusters to run on all clusters.",
        rich_help_panel="Kubernetes Settings",
    ),
    all_clusters: bool = typer.Option(
        False,
        "--all-clusters",
        help="Run on all clusters. Overrides --context.",
        rich_help_panel="Kubernetes Settings",
    ),
    namespaces: List[str] = typer.Option(
        None,
        "--namespace",
        "-n",
        help="List of namespaces to run on. By default, will run on all namespaces except 'kube-system'.",
        rich_help_panel="Kubernetes Settings",
    ),
    resources: List[str] = typer.Option(
        None,
        "--resource",
        "-r",
        help="List of resources to run on (Deployment, StatefulSet, DaemonSet, Job, Rollout). By default, will run on all resources. Case insensitive.",
        rich_help_panel="Kubernetes Settings",
    ),
    selector: Optional[str] = typer.Option(
        None,
        "--selector",
        "-s",
        help="Selector (label query) to filter on, supports '=', '==', and '!='.(e.g. -s key1=value1,key2=value2). Matching objects must satisfy all of the specified label constraints.",
        rich_help_panel="Kubernetes Settings",
    ),
    prometheus_url: Optional[str] = typer.Option(
        None,
        "--prometheus-url",
        "-p",
        help="Prometheus URL. If not provided, will attempt to find it in kubernetes cluster",
        rich_help_panel="Prometheus Settings",
    ),
    prometheus_auth_header: Optional[str] = typer.Option(
        None,
        "--prometheus-auth-header",
        help="Prometheus authentication header.",
        rich_help_panel="Prometheus Settings",
    ),
    prometheus_other_headers: Optional[List[str]] = typer.Option(
        None,
        "--prometheus-headers",
        "-H",
        help="Additional headers to add to Prometheus requests. Format as 'key: value', for example 'X-MyHeader: 123'. Trailing whitespaces will be stripped.",
        rich_help_panel="Prometheus Settings",
    ),
    prometheus_ssl_enabled: bool = typer.Option(
        False,
        "--prometheus-ssl-enabled",
        help="Enable SSL for Prometheus requests.",
        rich_help_panel="Prometheus Settings",
    ),
    prometheus_cluster_label: Optional[str] = typer.Option(
        None,
        "--prometheus-cluster-label",
        "-l",
        help="The label in prometheus for your cluster.(Only relevant for centralized prometheus)",
        rich_help_panel="Prometheus Settings",
    ),
    prometheus_label: str = typer.Option(
        None,
        "--prometheus-label",
        help="The label in prometheus used to differentiate clusters. (Only relevant for centralized prometheus)",
        rich_help_panel="Prometheus Settings",
    ),
    eks_managed_prom: bool = typer.Option(
        False,
        "--eks-managed-prom",
        help="Adds additional signitures for eks prometheus connection.",
        rich_help_panel="Prometheus EKS Settings",
    ),
    eks_managed_prom_profile_name: Optional[str] = typer.Option(
        None,
        "--eks-profile-name",
        help="Sets the profile name for eks prometheus connection.",
        rich_help_panel="Prometheus EKS Settings",
    ),
    eks_access_key: Optional[str] = typer.Option(
        None,
        "--eks-access-key",
        help="Sets the access key for eks prometheus connection.",
        rich_help_panel="Prometheus EKS Settings",
    ),
    eks_secret_key: Optional[str] = typer.Option(
        None,
        "--eks-secret-key",
        help="Sets the secret key for eks prometheus connection.",
        rich_help_panel="Prometheus EKS Settings",
    ),
    eks_service_name: Optional[str] = typer.Option(
        "aps",
        "--eks-service-name",
        help="Sets the service name for eks prometheus connection.",
        rich_help_panel="Prometheus EKS Settings",
    ),
    eks_managed_prom_region: Optional[str] = typer.Option(
        None,
        "--eks-managed-prom-region",
        help="Sets the region for eks prometheus connection.",
        rich_help_panel="Prometheus EKS Settings",
    ),
    coralogix_token: Optional[str] = typer.Option(
        None,
        "--coralogix-token",
        help="Adds the token needed to query Coralogix managed prometheus.",
        rich_help_panel="Prometheus Coralogix Settings",
    ),
    openshift: bool = typer.Option(
        False,
        "--openshift",
        help="Used when running by Robusta inside an OpenShift cluster.",
        rich_help_panel="Prometheus Openshift Settings",
        hidden=True,
    ),
    max_workers: int = typer.Option(
        10,
        "--max-workers",
        "-w",
        help="Max workers to use for async requests.",
        rich_help_panel="Threading Settings",
    ),
    format: str = typer.Option(
        "table",
        "--formatter",
        "-f",
        help=f"Output formatter ({', '.join(formatters.list_available())})",
        rich_help_panel="Logging Settings",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose mode", rich_help_panel="Logging Settings"
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Enable quiet mode", rich_help_panel="Logging Settings"
    ),
    log_to_stderr: bool = typer.Option(
        False, "--logtostderr", help="Pass logs to stderr", rich_help_panel="Logging Settings"
    ),
    width: Optional[int] = typer.Option(
        None,
        "--width",
        help="Width of the output. Will use console width by default.",
        rich_help_panel="Logging Settings",
    ),
    file_output: Optional[str] = typer.Option(
        None, "--fileoutput", help="Print the output to a file", rich_help_panel="Output Settings"
    ),
    slack_output: Optional[str] = typer.Option(
        None,
        "--slackoutput",
        help="Send to output to a slack channel, must have SLACK_BOT_TOKEN",
        rich_help_panel="Output Settings",
    ),
    cpu_min_value: int = __pydantic_field_to_typer_option(
        ["--cpu-min", "--cpu_min"],
        "Strategy Settings",
        Config.__fields__["cpu_min_value"]
    ),
    memory_min_value: int = __pydantic_field_to_typer_option(
        ["--mem-min", "--mem_min"],
        "Strategy Settings",
        Config.__fields__["memory_min_value"]
    ),
    history_duration: int = __pydantic_field_to_typer_option(
        ["--history-duration", "--history_duration"],
        "Strategy Settings",
        StrategySettings.__fields__["history_duration"]
    ),
    timeframe_duration: float = __pydantic_field_to_typer_option(
        ["--timeframe-duration", "--timeframe_duration"],
        "Strategy Settings",
        StrategySettings.__fields__["timeframe_duration"]
    ),
    cpu_percentile: float = __pydantic_field_to_typer_option(
        ["--cpu-percentile", "--cpu_percentile"],
        "Strategy Settings",
        SimpleStrategySettings.__fields__["cpu_percentile"]
    ),
    memory_buffer_percentage: int = __pydantic_field_to_typer_option(
        ["--memory-buffer-percentage", "--memory_buffer_percentage"],
        "Strategy Settings",
        SimpleStrategySettings.__fields__["memory_buffer_percentage"]
    ),
) -> None:
    """Run KRR using the `simple` strategy"""

    try:
        strategy_settings = SimpleStrategySettings(
            history_duration=history_duration,
            timeframe_duration=timeframe_duration,
            cpu_percentile=cpu_percentile,
            memory_buffer_percentage=memory_buffer_percentage,
        )
        strategy = SimpleStrategy(strategy_settings)
        config = Config(
            kubeconfig=kubeconfig,
            impersonate_user=impersonate_user,
            impersonate_group=impersonate_group,
            clusters="*" if all_clusters else clusters,
            namespaces="*" if "*" in namespaces else namespaces,
            resources="*" if "*" in resources else resources,
            selector=selector,
            prometheus_url=prometheus_url,
            prometheus_auth_header=prometheus_auth_header,
            prometheus_other_headers=prometheus_other_headers,
            prometheus_ssl_enabled=prometheus_ssl_enabled,
            prometheus_cluster_label=prometheus_cluster_label,
            prometheus_label=prometheus_label,
            eks_managed_prom=eks_managed_prom,
            eks_managed_prom_region=eks_managed_prom_region,
            eks_managed_prom_profile_name=eks_managed_prom_profile_name,
            eks_access_key=eks_access_key,
            eks_secret_key=eks_secret_key,
            eks_service_name=eks_service_name,
            coralogix_token=coralogix_token,
            openshift=openshift,
            max_workers=max_workers,
            format=format,
            verbose=verbose,
            cpu_min_value=cpu_min_value,
            memory_min_value=memory_min_value,
            quiet=quiet,
            log_to_stderr=log_to_stderr,
            width=width,
            file_output=file_output,
            slack_output=slack_output,
            strategy="simple",
        )
        Config.set_config(config)
    except ValidationError:
        logger.exception("Error occured while parsing arguments")
    else:
        runner = Runner(strategy)
        asyncio.run(runner.run())
