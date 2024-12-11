import itertools
from tabulate import tabulate
from typing import Any

from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.allocations import RecommendationValue, format_recommendation_value, format_diff, NONE_LITERAL, NAN_LITERAL
from robusta_krr.core.models.result import ResourceScan, ResourceType, Result
from robusta_krr.core.models.config import settings
from robusta_krr.utils import resource_units


def _format_request_str(item: ResourceScan, resource: ResourceType, selector: str) -> str:
    allocated = getattr(item.object.allocations, selector)[resource]
    info = item.recommended.info.get(resource)
    recommended = getattr(item.recommended, selector)[resource]
    severity = recommended.severity

    if allocated is None and recommended.value is None:
        return f"{NONE_LITERAL}"

    diff = format_diff(allocated, recommended, selector)
    if diff != "":
        diff = f"({diff})"

    if info is None:
        info_formatted = ""
    else:
        info_formatted = f"*({info})*"

    return (
        f"{severity.emoji} "
        + diff
        + " "
        + format_recommendation_value(allocated)
        + " -> "
        + format_recommendation_value(recommended.value)
        + " "
        + info_formatted
    )


def _format_total_diff(item: ResourceScan, resource: ResourceType, pods_current: int) -> str:
    selector = "requests"
    allocated = getattr(item.object.allocations, selector)[resource]
    recommended = getattr(item.recommended, selector)[resource]

    # if we have more than one pod, say so (this explains to the user why the total is different than the recommendation)
    if pods_current == 1:
        pods_info = ""
    else:
        pods_info = f"*({pods_current} pods)*"

    return f"{format_diff(allocated, recommended, selector, pods_current)} {pods_info}"


@formatters.register()
def markdown(result: Result) -> str:
    """Format the result as markdown.

    :param result: The result to format.
    :type result: :class:`core.result.Result`
    :returns: The formatted results.
    :rtype: str
    """

    cluster_count = len(set(item.object.cluster for item in result.scans))

    headers = []
    headers.append("Number")
    if cluster_count > 1 or settings.show_cluster_name:
        headers.append("Cluster")
    headers.append("Namespace")
    headers.append("Name")
    headers.append("Pods")
    headers.append("Old Pods")
    headers.append("Type")
    headers.append("Container")
    for resource in ResourceType:
        headers.append(f"{resource.name} Diff")
        headers.append(f"{resource.name} Requests")
        headers.append(f"{resource.name} Limits")

    table = []
    for _, group in itertools.groupby(
        enumerate(result.scans), key=lambda x: (x[1].object.cluster, x[1].object.namespace, x[1].object.name)
    ):
        group_items = list(group)

        for j, (i, item) in enumerate(group_items):
            last_row = j == len(group_items) - 1
            full_info_row = j == 0

            cells: list[Any] = [f"{i + 1}."]
            if cluster_count > 1 or settings.show_cluster_name:
                cells.append(item.object.cluster if full_info_row else "")
            cells += [
                item.object.namespace if full_info_row else "",
                item.object.name if full_info_row else "",
                f"{item.object.current_pods_count}" if full_info_row else "",
                f"{item.object.deleted_pods_count}" if full_info_row else "",
                item.object.kind if full_info_row else "",
                item.object.container
            ]

            for resource in ResourceType:
                cells.append(_format_total_diff(item, resource, item.object.current_pods_count))
                cells += [_format_request_str(item, resource, selector) for selector in ["requests", "limits"]]

            table.append(cells)

    return tabulate(table, headers, tablefmt="pipe")
