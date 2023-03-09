from __future__ import annotations

import abc
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from robusta_krr.core.models.result import Result


DEFAULT_FORMATTERS_PATH = os.path.join(os.path.dirname(__file__), "formatters")


class BaseFormatter(abc.ABC):
    """Base class for result formatters."""

    __display_name__: str

    def __str__(self) -> str:
        return self.__display_name__.title()

    @abc.abstractmethod
    def format(self, result: Result) -> Any:
        """Format the result.

        Args:
            result: The result to format.

        Returns:
            The formatted result.
        """

    @staticmethod
    def find(name: str) -> type[BaseFormatter]:
        """Get a strategy from its name."""

        # NOTE: Load default formatters
        from robusta_krr import formatters as _  # noqa: F401

        formatters = {cls.__display_name__.lower(): cls for cls in BaseFormatter.__subclasses__()}
        if name.lower() in formatters:
            return formatters[name.lower()]

        raise ValueError(f"Unknown formatter name: {name}. Available formatters: {', '.join(formatters)}")


__all__ = ["BaseFormatter"]
