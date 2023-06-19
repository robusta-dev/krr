from __future__ import annotations

import asyncio
import textwrap
from datetime import datetime
from typing import List, Literal, Optional, Union
from uuid import UUID

import typer
import urllib3

from robusta_krr import formatters as concrete_formatters  # noqa: F401
from robusta_krr.core.abstract import formatters
from robusta_krr.core.abstract.strategies import AnyStrategy, BaseStrategy
from robusta_krr.core.models.config import Config
from robusta_krr.core.runner import Runner
from robusta_krr.utils.version import get_version

app = typer.Typer(pretty_exceptions_show_locals=False, pretty_exceptions_short=True, no_args_is_help=True)

# NOTE: Disable insecure request warnings, as it might be expected to use self-signed certificates inside the cluster
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@app.command(rich_help_panel="Utils")
def version() -> None:
    typer.echo(get_version())


def __process_type(_T: type) -> str:
    """Process type to a python literal"""
    if _T in (int, float, str, bool, datetime, UUID):
        return _T.__name__
    elif _T is Optional:
        return f"Optional[{__process_type(_T.__args__[0])}]"  # type: ignore
    else:
        return "str"  # It the type is unknown, just use str and let pydantic handle it


def load_commands() -> None:
    for strategy_name, strategy_type in BaseStrategy.get_all().items():  # type: ignore
        FUNC_TEMPLATE = textwrap.dedent(
            """
            @app.command(rich_help_panel="Strategies")
            def {func_name}(
                ctx: typer.Context,
                kubeconfig: Optional[str] = typer.Option(
                    None,
                    "--kubeconfig",
                    "-k",
                    help="Path to kubeconfig file. If not provided, will attempt to find it.",
                    rich_help_panel="Kubernetes Settings"
                ),
                clusters: List[str] = typer.Option(
                    None,
                    "--context",
                    "--cluster",
                    "-c",
                    help="List of clusters to run on. By default, will run on the current cluster. Use --all-clusters to run on all clusters.",
                    rich_help_panel="Kubernetes Settings"
                ),
                all_clusters: bool = typer.Option(
                    False,
                    "--all-clusters",
                    help="Run on all clusters. Overrides --context.",
                    rich_help_panel="Kubernetes Settings"
                ),
                namespaces: List[str] = typer.Option(
                    None,
                    "--namespace",
                    "-n",
                    help="List of namespaces to run on. By default, will run on all namespaces.",
                    rich_help_panel="Kubernetes Settings"
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
                    'cluster',
                    "--prometheus-label",
                    help="The label in prometheus used to differentiate clusters. (Only relevant for centralized prometheus)",
                    rich_help_panel="Prometheus Settings",
                ),
                format: str = typer.Option("table", "--formatter", "-f", help="Output formatter ({formatters})", rich_help_panel="Logging Settings"),
                verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose mode", rich_help_panel="Logging Settings"),
                quiet: bool = typer.Option(False, "--quiet", "-q", help="Enable quiet mode", rich_help_panel="Logging Settings"),
                log_to_stderr: bool = typer.Option(False, "--logtostderr", help="Pass logs to stderr", rich_help_panel="Logging Settings"),
                file_output: Optional[str] = typer.Option(None, "--fileoutput", help="Print to file", rich_help_panel="Output Settings"),
                slack_output: Optional[str] = typer.Option(None, "--slackoutput", help="Send to slack", rich_help_panel="Output Settings"),
                {strategy_settings},
            ) -> None:
                '''Run KRR using the `{func_name}` strategy'''

                config = Config(
                    kubeconfig=kubeconfig,
                    clusters="*" if all_clusters else clusters,
                    namespaces="*" if "*" in namespaces else namespaces,
                    prometheus_url=prometheus_url,
                    prometheus_auth_header=prometheus_auth_header,
                    prometheus_ssl_enabled=prometheus_ssl_enabled,
                    prometheus_cluster_label=prometheus_cluster_label,
                    prometheus_label=prometheus_label,
                    format=format,
                    verbose=verbose,
                    quiet=quiet,
                    log_to_stderr=log_to_stderr,
                    file_output=file_output,
                    slack_output=slack_output,
                    strategy="{func_name}",
                    other_args={strategy_args},
                )
                runner = Runner(config)
                asyncio.run(runner.run())
            """
        )

        exec(
            FUNC_TEMPLATE.format(
                func_name=strategy_name,
                strategy_name=strategy_type.__name__,
                strategy_settings=",\n".join(
                    f'{field_name}: {__process_type(field_meta.type_)} = typer.Option({field_meta.default!r}, "--{field_name}", help="{field_meta.field_info.description}", rich_help_panel="Strategy Settings")'
                    for field_name, field_meta in strategy_type.get_settings_type().__fields__.items()
                ),
                strategy_args="{"
                + ",\n".join(
                    f"'{field_name}': {field_name}" for field_name in strategy_type.get_settings_type().__fields__
                )
                + "}",
                formatters=", ".join(formatters.list_available()),
            ),
            globals()
            | {strategy.__name__: strategy for strategy in AnyStrategy.get_all().values()}  # Defined strategies
            | {
                "Runner": Runner,
                "Config": Config,
                "List": List,
                "Optional": Optional,
                "Union": Union,
                "Literal": Literal,
                "asyncio": asyncio,
                "typer": typer,
                # Required imports, here to make the linter happy (it doesn't know that exec will use them)
            },
            locals(),
        )


def run() -> None:
    load_commands()
    app()


if __name__ == "__main__":
    run()
