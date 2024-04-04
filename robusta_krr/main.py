from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import typer
import urllib3
from pydantic import ValidationError  # noqa: F401
from typer.models import OptionInfo

from robusta_krr import formatters as concrete_formatters  # noqa: F401
from robusta_krr.core.abstract import formatters
from robusta_krr.core.abstract.strategies import BaseStrategy
from robusta_krr.core.models.config import Config
from robusta_krr.core.runner import Runner
from robusta_krr.utils.version import get_version

from .cli import add_strategy_command_to_app

app = typer.Typer(pretty_exceptions_show_locals=False, pretty_exceptions_short=True, no_args_is_help=True)

# NOTE: Disable insecure request warnings, as it might be expected to use self-signed certificates inside the cluster
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("krr")


@app.command(rich_help_panel="Utils")
def version() -> None:
    typer.echo(get_version())


def load_commands() -> None:
    for strategy_name, strategy_type in BaseStrategy.get_all().items():  # type: ignore
        add_strategy_command_to_app(app, strategy_name, strategy_type)


def run() -> None:
    load_commands()
    app()


if __name__ == "__main__":
    run()
