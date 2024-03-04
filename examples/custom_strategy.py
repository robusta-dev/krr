# This is an example on how to create your own custom strategy
import pydantic as pd
from typing import List, Optional

import asyncio
import typer
from pydantic import ValidationError

from robusta_krr.api.models import K8sObjectData, MetricsPodData, ResourceRecommendation, ResourceType, RunResult
from robusta_krr.core.models.config import Config, option_kubeconfig, option_clusters, option_all_clusters, option_namespaces, option_resources, option_selector, option_prometheus_url, option_prometheus_auth_header, option_prometheus_other_headers, option_prometheus_ssl_enabled, option_prometheus_cluster_label, option_prometheus_label, option_eks_managed_prom, option_eks_managed_prom_profile_name, option_eks_access_key, option_eks_secret_key, option_eks_service_name, option_eks_managed_prom_region, option_coralogix_token, option_openshift, option_max_workers, option_format, option_verbose, option_quiet, option_log_to_stderr, option_width, option_file_output, option_slack_output, option_cpu_min_value, option_memory_min_value
from robusta_krr.api.strategies import BaseStrategy, StrategySettings
from robusta_krr.core.integrations.prometheus.metrics import MaxMemoryLoader, PercentileCPULoader
from robusta_krr.main import app, logger
from robusta_krr.core.runner import Runner


# Providing description to the settings will make it available in the CLI help
class CustomStrategySettings(StrategySettings):
    param_1: float = pd.Field(99, gt=0, description="First example parameter")
    param_2: float = pd.Field(105_000, gt=0, description="Second example parameter")


class CustomStrategy(BaseStrategy):
    """
    A custom strategy that uses the provided parameters for CPU and memory.
    Made only in order to demonstrate how to create a custom strategy.
    """

    def __init__(self, settings: CustomStrategySettings):
        super().__init__(settings=settings)
        self.settings = settings

    display_name = "custom"  # The name of the strategy
    rich_console = True  # Whether to use rich console for the CLI
    metrics = [PercentileCPULoader(90), MaxMemoryLoader]  # The metrics to use for the strategy

    def run(self, history_data: MetricsPodData, object_data: K8sObjectData) -> RunResult:
        return {
            ResourceType.CPU: ResourceRecommendation(request=self.settings.param_1, limit=None),
            ResourceType.Memory: ResourceRecommendation(request=self.settings.param_2, limit=self.settings.param_2),
        }


# add a new command - much of this is boilerplate
@app.command(rich_help_panel="Strategies")
def custom(
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

    # define parameters that are specific to this strategy
    param1: float = typer.Option(
        None,
        "--param1",
        help="Explanation of param1",
        rich_help_panel="Strategy Settings",
    ),
    param2: float = typer.Option(
        None,
        "--param2",
        help="Explanation of param2",
        rich_help_panel="Strategy Settings",
    )
) -> None:
    """A custom strategy for KRR"""
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
        strategy_settings = CustomStrategySettings(
            param_1=param1,
            param_2=param2
        )
    except ValidationError:
        logger.exception("Error occured while parsing arguments")
    else:
        strategy = CustomStrategy(strategy_settings)
        runner = Runner(strategy)
        asyncio.run(runner.run())


# Running this file will register the strategy and make it available to the CLI
# Run it as `python ./custom_strategy.py custom --param1 2.0 --param2 1.0`
if __name__ == "__main__":
    app()
