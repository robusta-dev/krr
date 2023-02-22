from typing import Optional

import typer

from robusta_krr.core.config import Config
from robusta_krr.core.runner import Runner
from robusta_krr.utils.version import get_version
from robusta_krr.core.formatters import FormatType

app = typer.Typer()


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
    format: FormatType = typer.Option("text", "--formatter", "-f", help="Output formatter"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose mode"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Enable quiet mode"),
) -> None:
    config = Config(
        prometheus_url=prometheus_url,
        format=format,
        verbose=verbose,
        quiet=quiet,
    )
    runner = Runner(config)
    runner.run()


if __name__ == "__main__":
    app()
