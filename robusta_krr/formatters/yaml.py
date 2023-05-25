from __future__ import annotations

import json

import yaml

from robusta_krr.core.abstract.formatters import BaseFormatter
from robusta_krr.core.models.result import Result


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
        return yaml.dump(json.loads(result.json()), sort_keys=False)
