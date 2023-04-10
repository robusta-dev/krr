from __future__ import annotations

import abc
import os
from typing import TYPE_CHECKING, Any, TypeVar

from robusta_krr.utils.display_name import add_display_name

if TYPE_CHECKING:
    from robusta_krr.core.models.result import Result


DEFAULT_FORMATTERS_PATH = os.path.join(os.path.dirname(__file__), "formatters")


Self = TypeVar("Self", bound="BaseFormatter")


@add_display_name(postfix="Formatter")
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

    @classmethod
    def get_all(cls: type[Self]) -> dict[str, type[Self]]:
        """Get all available formatters."""

        # NOTE: Load default formatters
        from robusta_krr import formatters as _  # noqa: F401

        return {sub_cls.__display_name__.lower(): sub_cls for sub_cls in cls.__subclasses__()}

    @staticmethod
    def find(name: str) -> type[BaseFormatter]:
        """Get a strategy from its name."""

        formatters = BaseFormatter.get_all()

        l_name = name.lower()
        if l_name in formatters:
            return formatters[l_name]

        raise ValueError(f"Unknown formatter name: {name}. Available formatters: {', '.join(formatters)}")


__all__ = ["BaseFormatter"]
