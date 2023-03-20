from __future__ import annotations

from pprint import pformat

from robusta_krr.core.abstract.formatters import BaseFormatter
from robusta_krr.core.models.result import Result


class PPrintFormatter(BaseFormatter):
    """Formatter for object output with python's pprint module."""

    __display_name__ = "pprint"

    def format(self, result: Result) -> str:
        """Format the result using pprint.pformat(...)

        :param result: The results to format.
        :type result: :class:`core.result.Result`
        :returns: The formatted results.
        :rtype: str
        """

        return pformat(result.dict())
