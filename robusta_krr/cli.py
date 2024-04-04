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

app = typer.Typer(pretty_exceptions_show_locals=False, pretty_exceptions_short=True, no_args_is_help=True)

# NOTE: Disable insecure request warnings, as it might be expected to use self-signed certificates inside the cluster
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger("krr")


def __process_type(_T: type) -> type:
    """Process type to a python literal"""
    if _T in (int, float, str, bool, datetime, UUID):
        return _T
    elif _T is Optional:
        return Optional[{__process_type(_T.__args__[0])}]  # type: ignore
    else:
        return str  # If the type is unknown, just use str and let pydantic handle it


def _add_default_settings_to_command(run_strategy):
    """Modify the signature of the run_strategy function to include the strategy settings as keyword-only arguments."""

    signature = inspect.signature(run_strategy)
    run_strategy.__signature__ = signature.replace(  # type: ignore
        parameters=list(signature.parameters.values())[:-1]
        + [
            inspect.Parameter(
                name=field_name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=OptionInfo(
                    default=field_meta.default,
                    param_decls=field_meta.field_info.extra.get(
                        "typer__param_decls", list(set([f"--{field_name.replace('_', '-')}"]))
                    ),
                    help=field_meta.field_info.extra.get("typer__help", f"{field_meta.field_info.description}"),
                    rich_help_panel=field_meta.field_info.extra.get("typer__rich_help_panel", "General Settings"),
                ),
                annotation=__process_type(field_meta.type_),
            )
            for field_name, field_meta in Config.__fields__.items()
        ]
    )


def _add_strategy_settings_to_command(run_strategy, strategy_type: BaseStrategy):
    """Modify the signature of the run_strategy function to include the strategy settings as keyword-only arguments."""

    signature = inspect.signature(run_strategy)
    run_strategy.__signature__ = signature.replace(  # type: ignore
        parameters=list(signature.parameters.values())
        + [
            inspect.Parameter(
                name=field_name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                default=OptionInfo(
                    default=field_meta.default,
                    param_decls=list(set([f"--{field_name}", f"--{field_name.replace('_', '-')}"])),
                    help=f"{field_meta.field_info.description}",
                    rich_help_panel="Strategy Settings",
                ),
                annotation=__process_type(field_meta.type_),
            )
            for field_name, field_meta in strategy_type.get_settings_type().__fields__.items()
        ]
    )


def add_strategy_command_to_app(app: typer.Typer, strategy_name: str, StrategyType: BaseStrategy) -> None:
    def strategy_wrapper():
        def run_strategy(ctx: typer.Context, **kwargs) -> None:
            f"""Run KRR using the `{strategy_name}` strategy"""

            try:
                config = Config(**kwargs)
                strategy_settings = StrategyType.get_settings_type()(**kwargs)
            except ValidationError:
                logger.exception("Error occured while parsing arguments")
            else:
                Config.set_config(config)
                strategy = StrategyType(strategy_settings)

                runner = Runner(strategy)
                exit_code = asyncio.run(runner.run())
                raise typer.Exit(code=exit_code)

        run_strategy.__name__ = strategy_name
        _add_default_settings_to_command(run_strategy)
        _add_strategy_settings_to_command(run_strategy, StrategyType)

        app.command(rich_help_panel="Strategies")(run_strategy)

    strategy_wrapper()
