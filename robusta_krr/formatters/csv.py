import itertools
import csv

import logging


from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.allocations import RecommendationValue
from robusta_krr.core.models.result import ResourceScan, ResourceType, Result
from robusta_krr.utils import resource_units
import datetime

logger = logging.getLogger("krr")

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
        diff_sign = "+" if diff_val >= 0 else "-"
        return f"{diff_sign}{_format(abs(diff_val) * multiplier)}"


def _format_request_str(item: ResourceScan, resource: ResourceType, selector: str) -> str:
    allocated = getattr(item.object.allocations, selector)[resource]
    recommended = getattr(item.recommended, selector)[resource]

    if allocated is None and recommended.value is None:
        return f"{NONE_LITERAL}"

    diff = __calc_diff(allocated, recommended, selector)
    if diff != "":
        diff = f"({diff}) "

    return (
        diff
        + _format(allocated)
        + " -> "
        + _format(recommended.value)
    )


def _format_total_diff(item: ResourceScan, resource: ResourceType, pods_current: int) -> str:
    selector = "requests"
    allocated = getattr(item.object.allocations, selector)[resource]
    recommended = getattr(item.recommended, selector)[resource]

    return __calc_diff(allocated, recommended, selector, pods_current)


@formatters.register()
def csv_export(result: Result) -> str:
    
    current_datetime = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    file_path = f"krr-{current_datetime}.csv"

    # We need to order the resource columns so that they are in the format of Namespace,Name,Pods,Old Pods,Type,Container,CPU Diff,CPU Requests,CPU Limits,Memory Diff,Memory Requests,Memory Limits
    resource_columns = []
    for resource in ResourceType:
        resource_columns.append(f"{resource.name} Diff")
        resource_columns.append(f"{resource.name} Requests")
        resource_columns.append(f"{resource.name} Limits")

    with open(file_path, 'w+', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
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
             
    logger.info("CSV File: %s", file_path)
    return ""