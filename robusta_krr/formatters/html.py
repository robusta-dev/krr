from rich.console import Console

from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.result import Result
from .table import table

@formatters.register("html")
def html(result: Result) -> str:
    html_width = 250
    console = Console(record=True, width=html_width, force_terminal=False)
    table_output = table(result)
    console.print(table_output)
    return console.export_html(inline_styles=True)
