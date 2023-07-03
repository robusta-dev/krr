import itertools
from typing import Any, Optional

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


def __calc_diff(allocated, recommended, selector, multiplier=1) -> str:
    if recommended is None or isinstance(recommended.value, str) or selector != "requests":
        return ""
    else:
        reccomended_val = recommended.value if isinstance(recommended.value, (int, float)) else 0
        allocated_val = allocated if isinstance(allocated, (int, float)) else 0
        diff_val = reccomended_val - allocated_val
        diff_sign = "[green]+[/green]" if diff_val >= 0 else "[red]-[/red]"
        return f"{diff_sign}{_format(abs(diff_val) * multiplier)}"


def _format_request_str(item: ResourceScan, resource: ResourceType, selector: str) -> str:
    allocated = getattr(item.object.allocations, selector)[resource]
    info = item.recommended.info.get(resource)
    recommended = getattr(item.recommended, selector)[resource]
    severity = recommended.severity

    if allocated is None and recommended.value is None:
        return f"[{severity.color}]{NONE_LITERAL}[/{severity.color}]"

    diff = __calc_diff(allocated, recommended, selector)
    if diff != "":
        diff = f"({diff}) "

    return (
        diff
        + f"[{severity.color}]"
        + _format(allocated)
        + " -> "
        + _format(recommended.value)
        + f"[/{severity.color}]"
        + (f" [grey27]({info})[/grey27]" if info else "")
    )


def _format_total_diff(item: ResourceScan, resource: ResourceType, pods_current: int) -> str:
    selector = "requests"
    allocated = getattr(item.object.allocations, selector)[resource]
    recommended = getattr(item.recommended, selector)[resource]

    return __calc_diff(allocated, recommended, selector, pods_current)


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

    cluster_count = len(set(item.object.cluster for item in result.scans))

    table.add_column("Number", justify="right", no_wrap=True)
    if cluster_count > 1:
        table.add_column("Cluster", style="cyan")
    table.add_column("Namespace", style="cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Pods", style="cyan")
    table.add_column("Old Pods", style="cyan")
    table.add_column("Type", style="cyan")
    table.add_column("Container", style="cyan")
    for resource in ResourceType:
        table.add_column(f"{resource.name} Diff")
        table.add_column(f"{resource.name} Requests")
        table.add_column(f"{resource.name} Limits")

    for _, group in itertools.groupby(
        enumerate(result.scans), key=lambda x: (x[1].object.cluster, x[1].object.namespace, x[1].object.name)
    ):
        group_items = list(group)

        for j, (i, item) in enumerate(group_items):
            last_row = j == len(group_items) - 1
            full_info_row = j == 0

            cells: list[Any] = [f"[{item.severity.color}]{i + 1}.[/{item.severity.color}]"]
            if cluster_count > 1:
                cells.append(item.object.cluster if full_info_row else "")
            cells += [
                item.object.namespace if full_info_row else "",
                item.object.name if full_info_row else "",
                f"{item.object.current_pods_count}" if full_info_row else "",
                f"{item.object.deleted_pods_count}" if full_info_row else "",
                item.object.kind if full_info_row else "",
                item.object.container,
            ]

            for resource in ResourceType:
                cells.append(_format_total_diff(item, resource, item.object.current_pods_count))
                cells += [_format_request_str(item, resource, selector) for selector in ["requests", "limits"]]

            table.add_row(*cells, end_section=last_row)

    return table
