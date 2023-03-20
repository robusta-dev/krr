import asyncio
from typing import Optional

import typer
import urllib3

from robusta_krr.core.models.config import Config
from robusta_krr.core.runner import Runner
from robusta_krr.utils.version import get_version

app = typer.Typer(pretty_exceptions_show_locals=False, pretty_exceptions_short=True)

# NOTE: Disable insecure request warnings, as it might be expected to use self-signed certificates inside the cluster
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@app.command()
def version() -> None:
    typer.echo(get_version())


@app.command()
def run(
    prometheus_url: Optional[str] = typer.Option(
        None,
        "--prometheus-url",
        "-p",
        help="Prometheus URL. If not provided, will attempt to find it in kubernetes cluster",
    ),
    format: str = typer.Option("table", "--formatter", "-f", help="Output formatter"),
    strategy: str = typer.Option("simple", "--strategy", "-s", help="Strategy to use"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose mode"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Enable quiet mode"),
) -> None:
    config = Config(
        prometheus_url=prometheus_url,
        format=format,
        verbose=verbose,
        quiet=quiet,
        strategy=strategy,
    )
    runner = Runner(config)
    asyncio.run(runner.run())


if __name__ == "__main__":
    app()
