from __future__ import annotations

import itertools

from robusta_krr.core.abstract.formatters import BaseFormatter
from robusta_krr.core.models.result import Result, ResourceType
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

        for _, group in itertools.groupby(
            enumerate(result.scans), key=lambda x: (x[1].object.cluster, x[1].object.namespace, x[1].object.name)
        ):
            group_items = list(group)

            for j, (i, item) in enumerate(group_items):
                last_row = j == len(group_items) - 1
                full_info_row = j == 0

                table.add_row(
                    str(i),
                    item.object.cluster if full_info_row else "",
                    item.object.namespace if full_info_row else "",
                    item.object.name if full_info_row else "",
                    item.object.kind if full_info_row else "",
                    item.object.container,
                    *[
                        f"{getattr(item.object.allocations, selector)[resource]}"
                        + "->"
                        + f"{resource_units.format(getattr(item.recommended, selector)[resource])}"
                        for resource in ResourceType
                        for selector in ["requests", "limits"]
                    ],
                    end_section=last_row,
                )

        return table
