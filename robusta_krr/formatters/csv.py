import itertools
import csv
import logging
import io

from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.allocations import RecommendationValue, format_recommendation_value, format_diff, NONE_LITERAL, NAN_LITERAL
from robusta_krr.core.models.result import ResourceScan, ResourceType, Result

logger = logging.getLogger("krr")

def _format_request_str(item: ResourceScan, resource: ResourceType, selector: str) -> str:
    allocated = getattr(item.object.allocations, selector)[resource]
    recommended = getattr(item.recommended, selector)[resource]

    if allocated is None and recommended.value is None:
        return f"{NONE_LITERAL}"

    diff = format_diff(allocated, recommended, selector)
    if diff != "":
        diff = f"({diff}) "

    return (
        diff
        + format_recommendation_value(allocated)
        + " -> "
        + format_recommendation_value(recommended.value)
    )

def _format_total_diff(item: ResourceScan, resource: ResourceType, pods_current: int) -> str:
    selector = "requests"
    allocated = getattr(item.object.allocations, selector)[resource]
    recommended = getattr(item.recommended, selector)[resource]

    return format_diff(allocated, recommended, selector, pods_current)

@formatters.register("csv")
def csv_exporter(result: Result) -> str:
    # We need to order the resource columns so that they are in the format of Namespace,Name,Pods,Old Pods,Type,Container,CPU Diff,CPU Requests,CPU Limits,Memory Diff,Memory Requests,Memory Limits
    resource_columns = []
    for resource in ResourceType:
        resource_columns.append(f"{resource.name} Diff")
        resource_columns.append(f"{resource.name} Requests")
        resource_columns.append(f"{resource.name} Limits")

    output = io.StringIO()
    csv_writer = csv.writer(output)
    csv_writer.writerow([
        "Namespace", "Name", "Pods", "Old Pods", "Type", "Container",
        *resource_columns
    ])

    for _, group in itertools.groupby(
        enumerate(result.scans), key=lambda x: (x[1].object.cluster, x[1].object.namespace, x[1].object.name)
    ):
        group_items = list(group)

        for j, (i, item) in enumerate(group_items):
            full_info_row = j == 0

            row = [
                item.object.namespace if full_info_row else "",
                item.object.name if full_info_row else "",
                f"{item.object.current_pods_count}" if full_info_row else "",
                f"{item.object.deleted_pods_count}" if full_info_row else "",
                item.object.kind if full_info_row else "",
                item.object.container,
            ]

            for resource in ResourceType:
                row.append(_format_total_diff(item, resource, item.object.current_pods_count))
                row += [_format_request_str(item, resource, selector) for selector in ["requests", "limits"]]

            csv_writer.writerow(row)
             
    return output.getvalue()
