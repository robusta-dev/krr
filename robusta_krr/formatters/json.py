from __future__ import annotations

from robusta_krr.core.abstract.formatters import BaseFormatter
from robusta_krr.core.models.result import Result


class JSONFormatter(BaseFormatter):
    """Formatter for JSON output."""

    __display_name__ = "json"

    def format(self, result: Result) -> str:
        """Format the result as JSON.

        :param result: The results to format.
        :type result: :class:`core.result.Result`
        :returns: The formatted results.
        :rtype: str
        """

        return result.json(indent=2, models_as_dict=False)
