from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

import typer
import urllib3
from pydantic import ValidationError  # noqa: F401

from robusta_krr import formatters as concrete_formatters  # noqa: F401
from robusta_krr.core.abstract import formatters
from robusta_krr.core.abstract.strategies import StrategySettings
from robusta_krr.strategies.simple import SimpleStrategy, SimpleStrategySettings
from robusta_krr.core.models.config import Config, pydantic_field_to_typer_option, option_kubeconfig, option_clusters, option_all_clusters, option_namespaces, option_resources, option_selector, option_prometheus_url, option_prometheus_auth_header, option_prometheus_other_headers, option_prometheus_ssl_enabled, option_prometheus_cluster_label, option_prometheus_label, option_eks_managed_prom, option_eks_managed_prom_profile_name, option_eks_access_key, option_eks_secret_key, option_eks_service_name, option_eks_managed_prom_region, option_coralogix_token, option_openshift, option_max_workers, option_format, option_verbose, option_quiet, option_log_to_stderr, option_width, option_file_output, option_slack_output, option_cpu_min_value, option_memory_min_value

from robusta_krr.core.runner import Runner
from robusta_krr.utils.version import get_version

app = typer.Typer(pretty_exceptions_show_locals=False, pretty_exceptions_short=True, no_args_is_help=True)

# NOTE: Disable insecure request warnings, as it might be expected to use self-signed certificates inside the cluster
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("krr")


@app.command(rich_help_panel="Utils")
def version() -> None:
    typer.echo(get_version())


@app.command(name="simple", rich_help_panel="Strategies")
def run_simple(
    kubeconfig: Optional[str] = option_kubeconfig,
    clusters: List[str] = option_clusters,
    all_clusters: bool = option_all_clusters,
    namespaces: List[str] = option_namespaces,
    resources: List[str] = option_resources,
    selector: Optional[str] = option_selector,
    prometheus_url: Optional[str] = option_prometheus_url,
    prometheus_auth_header: Optional[str] = option_prometheus_auth_header,
    prometheus_other_headers: Optional[List[str]]= option_prometheus_other_headers,
    prometheus_ssl_enabled: bool = option_prometheus_ssl_enabled,
    prometheus_cluster_label: Optional[str] = option_prometheus_cluster_label,
    prometheus_label: str = option_prometheus_label,
    eks_managed_prom: bool = option_eks_managed_prom,
    eks_managed_prom_profile_name: Optional[str] = option_eks_managed_prom_profile_name,
    eks_access_key: Optional[str] = option_eks_access_key,
    eks_secret_key: Optional[str] = option_eks_secret_key,
    eks_service_name: Optional[str] = option_eks_service_name,
    eks_managed_prom_region: Optional[str] = option_eks_managed_prom_region,
    coralogix_token: Optional[str] = option_coralogix_token,
    openshift: bool = option_openshift,
    max_workers: int = option_max_workers,
    format: str = option_format,
    verbose: bool = option_verbose,
    quiet: bool = option_quiet,
    log_to_stderr: bool = option_log_to_stderr,
    width: Optional[int] = option_width,
    file_output: Optional[str] = option_file_output,
    slack_output: Optional[str] = option_slack_output,
    cpu_min_value: int = option_cpu_min_value,
    memory_min_value: int = option_memory_min_value,
    history_duration: int = pydantic_field_to_typer_option(
        ["--history-duration", "--history_duration"],
        "Strategy Settings",
        StrategySettings.__fields__["history_duration"]
    ),
    timeframe_duration: float = pydantic_field_to_typer_option(
        ["--timeframe-duration", "--timeframe_duration"],
        "Strategy Settings",
        StrategySettings.__fields__["timeframe_duration"]
    ),
    cpu_percentile: float = pydantic_field_to_typer_option(
        ["--cpu-percentile", "--cpu_percentile"],
        "Strategy Settings",
        SimpleStrategySettings.__fields__["cpu_percentile"]
    ),
    memory_buffer_percentage: int = pydantic_field_to_typer_option(
        ["--memory-buffer-percentage", "--memory_buffer_percentage"],
        "Strategy Settings",
        SimpleStrategySettings.__fields__["memory_buffer_percentage"]
    ),
) -> None:
    """Run KRR using the `simple` strategy"""
    try:
        config = Config(
            kubeconfig=kubeconfig,
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
        )
        Config.set_config(config)
        strategy_settings = SimpleStrategySettings(
            history_duration=history_duration,
            timeframe_duration=timeframe_duration,
            cpu_percentile=cpu_percentile,
            memory_buffer_percentage=memory_buffer_percentage,
        )
    except ValidationError:
        logger.exception("Error occured while parsing arguments")
    else:
        strategy = SimpleStrategy(strategy_settings)
        runner = Runner(strategy)
        asyncio.run(runner.run())
