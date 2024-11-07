import csv
import io
import itertools
import logging
from typing import Any

from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.allocations import NONE_LITERAL, format_diff, format_recommendation_value
from robusta_krr.core.models.config import settings
from robusta_krr.core.models.result import ResourceScan, ResourceType, Result

logger = logging.getLogger("krr")


NAMESPACE_HEADER = "Namespace"
NAME_HEADER = "Name"
PODS_HEADER = "Pods"
OLD_PODS_HEADER = "Old Pods"
TYPE_HEADER = "Type"
CONTAINER_HEADER = "Container"
CLUSTER_HEADER = "Cluster"
SEVERITY_HEADER = "Severity"

RESOURCE_DIFF_HEADER = "{resource_name} Diff"
RESOURCE_REQUESTS_HEADER = "{resource_name} Requests"
RESOURCE_LIMITS_HEADER = "{resource_name} Limits"


def _format_request_str(item: ResourceScan, resource: ResourceType, selector: str) -> str:
    allocated = getattr(item.object.allocations, selector)[resource]
    recommended = getattr(item.recommended, selector)[resource]

    if allocated is None and recommended.value is None:
        return f"{NONE_LITERAL}"

    diff = format_diff(allocated, recommended, selector)
    if diff != "":
        diff = f"({diff}) "

    return diff + format_recommendation_value(allocated) + " -> " + format_recommendation_value(recommended.value)


def _format_total_diff(item: ResourceScan, resource: ResourceType, pods_current: int) -> str:
    selector = "requests"
    allocated = getattr(item.object.allocations, selector)[resource]
    recommended = getattr(item.recommended, selector)[resource]

    return format_diff(allocated, recommended, selector, pods_current)


@formatters.register("csv")
def csv_exporter(result: Result) -> str:
    # We need to order the resource columns so that they are in the format of Namespace,Name,Pods,Old Pods,Type,Container,CPU Diff,CPU Requests,CPU Limits,Memory Diff,Memory Requests,Memory Limits
    csv_columns = ["Namespace", "Name", "Pods", "Old Pods", "Type", "Container"]

    if settings.show_cluster_name:
        csv_columns.insert(0, "Cluster")

    if settings.show_severity:
        csv_columns.append("Severity")

    for resource in ResourceType:
        csv_columns.append(RESOURCE_DIFF_HEADER.format(resource_name=resource.name))
        csv_columns.append(RESOURCE_REQUESTS_HEADER.format(resource_name=resource.name))
        csv_columns.append(RESOURCE_LIMITS_HEADER.format(resource_name=resource.name))

    output = io.StringIO()
    csv_writer = csv.DictWriter(output, csv_columns, extrasaction="ignore")
    csv_writer.writeheader()

    for _, group in itertools.groupby(
        enumerate(result.scans), key=lambda x: (x[1].object.cluster, x[1].object.namespace, x[1].object.name)
    ):
        group_items = list(group)

        for j, (_, item) in enumerate(group_items):
            full_info_row = j == 0

            row: dict[str, Any] = {
                NAMESPACE_HEADER: item.object.namespace if full_info_row else "",
                NAME_HEADER: item.object.name if full_info_row else "",
                PODS_HEADER: f"{item.object.current_pods_count}" if full_info_row else "",
                OLD_PODS_HEADER: f"{item.object.deleted_pods_count}" if full_info_row else "",
                TYPE_HEADER: item.object.kind if full_info_row else "",
                CONTAINER_HEADER: item.object.container,
                SEVERITY_HEADER: item.severity,
                CLUSTER_HEADER: item.object.cluster,
            }

            for resource in ResourceType:
                row[RESOURCE_DIFF_HEADER.format(resource_name=resource.name)] = _format_total_diff(
                    item, resource, item.object.current_pods_count
                )
                row[RESOURCE_REQUESTS_HEADER.format(resource_name=resource.name)] = _format_request_str(
                    item, resource, "requests"
                )
                row[RESOURCE_LIMITS_HEADER.format(resource_name=resource.name)] = _format_request_str(
                    item, resource, "limits"
                )

            csv_writer.writerow(row)

    return output.getvalue()
