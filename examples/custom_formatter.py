# This is an example on how to create your own custom formatter

from __future__ import annotations

import robusta_krr
from robusta_krr.api.formatters import BaseFormatter
from robusta_krr.api.models import Result


class CustomFormatter(BaseFormatter):
    # This is the name that will be used to reference the formatter in the CLI
    __display_name__ = "my_formatter"

    # This will pass the result to Rich Console for formatting.
    # By default, the result is passed to `print` function.
    # See https://rich.readthedocs.io/en/latest/ for more info
    __rich_console__ = True

    def format(self, result: Result) -> str:
        return "Custom formatter"


# Running this file will register the formatter and make it available to the CLI
# Run it as `python ./custom_formatter.py simple --formater my_formatter`
if __name__ == "__main__":
    robusta_krr.run()
