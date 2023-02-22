from __future__ import annotations
import abc

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from robusta_krr.core.result import Result


class BaseFormatter(abc.ABC):
    """Base class for result formatters."""

    @abc.abstractmethod
    def format(self, result: Result) -> str:
        """Format the result.

        Args:
            result: The result to format.

        Returns:
            The formatted result.
        """
        raise NotImplementedError
