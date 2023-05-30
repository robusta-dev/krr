from __future__ import annotations

from typing import Any, Callable, Optional

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


def register(
    display_name: Optional[str] = None, *, rich_console: bool = False
) -> Callable[[FormatterFunc], FormatterFunc]:
    """
    A decorator to register a formatter function.

    Args:
        display_name (str, optional): The name to use for the formatter in the registry.
        rich_console (bool): Whether or not the formatter is for a rich console. Defaults to False.

    Returns:
        Callable[[FormatterFunc], FormatterFunc]: The decorator function.
    """

    def decorator(func: FormatterFunc) -> FormatterFunc:
        name = display_name or func.__name__

        FORMATTERS_REGISTRY[name] = func

        func.__display_name__ = name  # type: ignore
        func.__rich_console__ = rich_console  # type: ignore

        return func

    return decorator


def find(name: str) -> FormatterFunc:
    """
    Find a formatter by name in the registry.

    Args:
        name (str): The name of the formatter.

    Returns:
        FormatterFunc: The formatter function.

    Raises:
        ValueError: If a formatter with the given name does not exist.
    """

    try:
        return FORMATTERS_REGISTRY[name]
    except KeyError as e:
        raise ValueError(f"Formatter '{name}' not found") from e


def list_available() -> list[str]:
    """
    List available formatters in the registry.

    Returns:
    list[str]: A list of the names of the available formatters.
    """

    return list(FORMATTERS_REGISTRY)


__all__ = ["register", "find"]
