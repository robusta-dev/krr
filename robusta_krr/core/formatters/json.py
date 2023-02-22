from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BaseFormatter

if TYPE_CHECKING:
    from robusta_krr.core.result import Result


class JSONFormatter(BaseFormatter):
    """Formatter for JSON output."""

    def format(self, result: Result) -> str:
        """Format the result as JSON.

        :param result: The results to format.
        :type result: :class:`core.result.Result`
        :returns: The formatted results.
        :rtype: str
        """
        raise NotImplementedError
