from __future__ import annotations

from robusta_krr.core.formatters import BaseFormatter
from robusta_krr.core.result import Result


class YAMLFormatter(BaseFormatter):
    """Formatter for YAML output."""

    __display_name__ = "yaml"

    def format(self, result: Result) -> str:
        """Format the result as YAML.

        :param result: The results to format.
        :type result: :class:`core.result.Result`
        :returns: The formatted results.
        :rtype: str
        """
        raise NotImplementedError
