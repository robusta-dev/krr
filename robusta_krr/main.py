from __future__ import annotations

import asyncio
import textwrap
from datetime import datetime
from typing import List, Optional, Literal, Union
from uuid import UUID

import typer
import urllib3

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


for strategy_name, strategy_type in BaseStrategy.get_all().items():  # type: ignore
    FUNC_TEMPLATE = textwrap.dedent(
        """
        @app.command(rich_help_panel="Strategies")
        def {func_name}(
            ctx: typer.Context,
            clusters: Optional[Union[List[str], Literal["*"]]] = typer.Option(
                None, 
                "--clusters", 
                "-c", 
                help="List of clusters to run on. By default, will run on the current cluster.", 
                rich_help_panel="Kubernetes Settings"
            ),
            namespaces: Optional[Union[List[str], Literal["*"]]] = typer.Option(
                None, 
                "--namespaces", 
                "-n", 
                help="List of clusters to run on. By default, will run on the current cluster.", 
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
            format: str = typer.Option("table", "--formatter", "-f", help="Output formatter", rich_help_panel="Logging Settings"),
            verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose mode", rich_help_panel="Logging Settings"),
            quiet: bool = typer.Option(False, "--quiet", "-q", help="Enable quiet mode", rich_help_panel="Logging Settings"),
            {strategy_settings},
        ) -> None:
            '''Run KubeKraken using the `{func_name}` strategy'''

            config = Config(
                clusters=clusters,
                namespaces=namespaces,
                prometheus_url=prometheus_url,
                prometheus_auth_header=prometheus_auth_header,
                prometheus_ssl_enabled=prometheus_ssl_enabled,
                format=format,
                verbose=verbose,
                quiet=quiet,
                strategy="{func_name}",
                other_args=ctx.args,
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
        },  # Required imports, here to make the linter happy (it doesn't know that exec will use them)
        locals(),
    )


if __name__ == "__main__":
    app()
