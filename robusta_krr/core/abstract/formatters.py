from __future__ import annotations

from typing import Any, Optional, Callable

from robusta_krr.core.models.result import Result


FormatterFunc = Callable[[Result], Any]

FORMATTERS_REGISTRY: dict[str, FormatterFunc] = {}


# NOTE: Here asterisk is used to make the argument `rich_console` keyword-only
#       This is done to avoid the following usage, where it is unclear what the boolean value is for:
#           @register("My Formatter", True)
#           def my_formatter(result: Result) -> str:
#               return "My formatter"
#
#       Instead, the following usage is enforced:
#           @register("My Formatter", rich_console=True)
#           def my_formatter(result: Result) -> str:
#               return "My formatter"

def register(display_name: Optional[str] = None, *, rich_console: bool = False) -> Callable[[FormatterFunc], FormatterFunc]:
    """Decorator to register a formatter."""

    def decorator(func: FormatterFunc) -> FormatterFunc:
        name = display_name or func.__name__

        FORMATTERS_REGISTRY[name] = func

        func.__display_name__ = name  # type: ignore
        func.__rich_console__ = rich_console  # type: ignore

        return func

    return decorator


def find(name: str) -> FormatterFunc:
    """Find a formatter by name."""

    try:
        return FORMATTERS_REGISTRY[name]
    except KeyError as e:
        raise ValueError(f"Formatter '{name}' not found") from e


def list_available() -> list[str]:
    """List available formatters."""

    return list(FORMATTERS_REGISTRY)


__all__ = ["register", "find"]
