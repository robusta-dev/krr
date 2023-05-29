import itertools

from rich.table import Table

from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.allocations import RecommendationValue
from robusta_krr.core.models.result import ResourceScan, ResourceType, Result
from robusta_krr.utils import resource_units

NONE_LITERAL = "unset"
NAN_LITERAL = "?"


def _format(value: RecommendationValue) -> str:
    if value is None:
        return NONE_LITERAL
    elif isinstance(value, str):
        return NAN_LITERAL
    else:
        return resource_units.format(value)


def _format_request_str(item: ResourceScan, resource: ResourceType, selector: str) -> str:
    allocated = getattr(item.object.allocations, selector)[resource]
    recommended = getattr(item.recommended, selector)[resource]
    severity = recommended.severity

    return f"[{severity.color}]" + _format(allocated) + " -> " + _format(recommended.value) + f"[/{severity.color}]"


@formatters.register(rich_console=True)
def table(result: Result) -> Table:
    """Format the result as text.

    :param result: The result to format.
    :type result: :class:`core.result.Result`
    :returns: The formatted results.
    :rtype: str
    """

    table = Table(
        show_header=True,
        header_style="bold magenta",
        title=f"\n{result.description}\n" if result.description else None,
        title_justify="left",
        title_style="",
        caption=f"{result.score} points - {result.score_letter}",
    )

    table.add_column("Number", justify="right", no_wrap=True)
    table.add_column("Cluster", style="cyan")
    table.add_column("Namespace", style="cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Pods", style="cyan")
    table.add_column("Old Pods", style="cyan")
    table.add_column("Type", style="cyan")
    table.add_column("Container", style="cyan")
    for resource in ResourceType:
        table.add_column(f"{resource.name} Requests")
        table.add_column(f"{resource.name} Limits")

    for _, group in itertools.groupby(
        enumerate(result.scans), key=lambda x: (x[1].object.cluster, x[1].object.namespace, x[1].object.name)
    ):
        group_items = list(group)

        for j, (i, item) in enumerate(group_items):
            last_row = j == len(group_items) - 1
            full_info_row = j == 0

            table.add_row(
                f"[{item.severity.color}]{i + 1}.[/{item.severity.color}]",
                item.object.cluster if full_info_row else "",
                item.object.namespace if full_info_row else "",
                item.object.name if full_info_row else "",
                f"{item.object.current_pods_count}" if full_info_row else "",
                f"{item.object.deleted_pods_count}" if full_info_row else "",
                item.object.kind if full_info_row else "",
                item.object.container,
                *[
                    _format_request_str(item, resource, selector)
                    for resource in ResourceType
                    for selector in ["requests", "limits"]
                ],
                end_section=last_row,
            )

    return table
