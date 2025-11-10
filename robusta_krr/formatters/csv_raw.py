import csv
import io
import logging
from typing import Any, Union

from robusta_krr.core.abstract import formatters
from robusta_krr.core.models.allocations import NAN_LITERAL, NONE_LITERAL
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

RESOURCE_REQUESTS_CURRENT_HEADER = "{resource_name} Requests Current"
RESOURCE_REQUESTS_RECOMMENDED_HEADER = '{resource_name} Requests Recommended'

RESOURCE_LIMITS_CURRENT_HEADER = "{resource_name} Limits Current"
RESOURCE_LIMITS_RECOMMENDED_HEADER = '{resource_name} Limits Recommended'


def _format_value(val: Union[float, int]) -> str:
    if isinstance(val, int):
        return str(val)
    elif isinstance(val, float):
        return str(int(val)) if val.is_integer() else str(val)
    elif val is None:
        return NONE_LITERAL
    elif isinstance(val, str):
        return NAN_LITERAL
    else:
        raise ValueError(f'unknown value: {val}')


def _format_request_current(item: ResourceScan, resource: ResourceType, selector: str) -> str:
    allocated = getattr(item.object.allocations, selector)[resource]
    if allocated is None:
        return NONE_LITERAL
    return _format_value(allocated)


def _format_request_recommend(item: ResourceScan, resource: ResourceType, selector: str) -> str:
    recommended = getattr(item.recommended, selector)[resource]
    if recommended is None:
        return NONE_LITERAL
    return _format_value(recommended.value)


@formatters.register("csv-raw")
def csv_raw(result: Result) -> str:
    # We need to order the resource columns so that they are in the format of
    # Namespace, Name, Pods, Old Pods, Type, Container,
    # CPU Requests Current, CPU Requests Recommend, CPU Limits Current, CPU Limits Recommend,
    # Memory Requests Current, Memory Requests Recommend, Memory Limits Current, Memory Limits Recommend,
    csv_columns = ["Namespace", "Name", "Pods", "Old Pods", "Type", "Container"]

    if settings.show_cluster_name:
        csv_columns.insert(0, "Cluster")

    if settings.show_severity:
        csv_columns.append("Severity")

    for resource in ResourceType:
        csv_columns.append(RESOURCE_REQUESTS_CURRENT_HEADER.format(resource_name=resource.name))
        csv_columns.append(RESOURCE_REQUESTS_RECOMMENDED_HEADER.format(resource_name=resource.name))
        csv_columns.append(RESOURCE_LIMITS_CURRENT_HEADER.format(resource_name=resource.name))
        csv_columns.append(RESOURCE_LIMITS_RECOMMENDED_HEADER.format(resource_name=resource.name))

    output = io.StringIO()
    csv_writer = csv.DictWriter(output, csv_columns, extrasaction="ignore")
    csv_writer.writeheader()

    for item in result.scans:
        row: dict[str, Any] = {
            NAMESPACE_HEADER: item.object.namespace,
            NAME_HEADER: item.object.name,
            PODS_HEADER: f"{item.object.current_pods_count}",
            OLD_PODS_HEADER: f"{item.object.deleted_pods_count}",
            TYPE_HEADER: item.object.kind,
            CONTAINER_HEADER: item.object.container,
            SEVERITY_HEADER: item.severity,
            CLUSTER_HEADER: item.object.cluster,
        }

        for resource in ResourceType:
            resource: ResourceType
            row[RESOURCE_REQUESTS_CURRENT_HEADER.format(resource_name=resource.name)] = _format_request_current(
                item, resource, "requests"
            )
            row[RESOURCE_REQUESTS_RECOMMENDED_HEADER.format(resource_name=resource.name)] = _format_request_recommend(
                item, resource, "requests"
            )
            row[RESOURCE_LIMITS_CURRENT_HEADER.format(resource_name=resource.name)] = _format_request_current(
                item, resource, "limits"
            )
            row[RESOURCE_LIMITS_RECOMMENDED_HEADER.format(resource_name=resource.name)] = _format_request_recommend(
                item, resource, "limits"
            )

        csv_writer.writerow(row)

    return output.getvalue()
