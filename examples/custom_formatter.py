# This is an example on how to create your own custom formatter

from __future__ import annotations

import robusta_krr
from robusta_krr.api.formatters import BaseFormatter
from robusta_krr.api.models import Result


class CustomFormatter(BaseFormatter):
    __display_name__ = "my_formatter"

    def format(self, result: Result) -> str:
        return "Custom formatter"


# Running this file will register the formatter and make it available to the CLI
# Run it as `python ./custom_formatter.py simple --formater my_formatter`
if __name__ == "__main__":
    robusta_krr.run()
