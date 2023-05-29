# This is an example on how to create your own custom formatter

from __future__ import annotations

import robusta_krr
from robusta_krr.api import formatters
from robusta_krr.api.models import Result


# This is a custom formatter
# It will be available to the CLI as `my_formatter`
# Rich console will be enabled in this case, so the output will be colored and formatted
@formatters.register(rich_console=True)
def my_formatter(result: Result) -> str:
    # Return custom formatter
    return "Custom formatter"


# Running this file will register the formatter and make it available to the CLI
# Run it as `python ./custom_formatter.py simple --formater my_formatter`
if __name__ == "__main__":
    robusta_krr.run()
