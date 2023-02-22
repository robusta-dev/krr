from __future__ import annotations
from typing import TYPE_CHECKING

from .base import BaseFormatter

if TYPE_CHECKING:
    from robusta_krr.core.result import Result


class TextFormatter(BaseFormatter):
    """Formatter for text output."""

    def format(self, result: Result) -> str:
        """Format the result as text.

        :param result: The result to format.
        :type result: :class:`core.result.Result`
        :returns: The formatted results.
        :rtype: str
        """
        return "Example result."
