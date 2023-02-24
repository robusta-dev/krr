from __future__ import annotations

from robusta_krr.core.formatters import BaseFormatter
from robusta_krr.core.result import Result


class TextFormatter(BaseFormatter):
    """Formatter for text output."""

    __display_name__ = "text"

    def format(self, result: Result) -> str:
        """Format the result as text.

        :param result: The result to format.
        :type result: :class:`core.result.Result`
        :returns: The formatted results.
        :rtype: str
        """
        return "Example result."
