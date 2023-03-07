from __future__ import annotations

from robusta_krr.core.formatters import BaseFormatter
from robusta_krr.core.result import Result, ResourceType
from robusta_krr.utils import resource_units

from rich.table import Table


class TableFormatter(BaseFormatter):
    """Formatter for text output."""

    __display_name__ = "table"

    def format(self, result: Result) -> Table:
        """Format the result as text.

        :param result: The result to format.
        :type result: :class:`core.result.Result`
        :returns: The formatted results.
        :rtype: str
        """

        table = Table(show_header=True, header_style="bold magenta", title=f"Scan result ({result.score} points)")

        table.add_column("Number", justify="right", style="dim", no_wrap=True)
        table.add_column("Cluster", style="cyan")
        table.add_column("Namespace", style="cyan")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="cyan")
        table.add_column("Container", style="cyan")
        for resource in ResourceType:
            table.add_column(f"{resource.name} Requests", style="green")
            table.add_column(f"{resource.name} Limits", style="green")

        for i, item in enumerate(result.scans):
            table.add_row(
                str(i),
                item.object.cluster,
                item.object.namespace,
                item.object.name,
                item.object.kind or "Unknown",
                item.object.container,
                *[
                    f"{getattr(item.current, selector)[resource]} -> {resource_units.format(getattr(item.recommended, selector)[resource])}"
                    for resource in ResourceType
                    for selector in ["requests", "limits"]
                ],
            )

        return table
