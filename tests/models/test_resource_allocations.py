from typing import Union

import pytest

from robusta_krr.core.models.allocations import ResourceAllocations, ResourceType


@pytest.mark.parametrize(
    "cpu",
    [
        {"request": "5m", "limit": None},
        {"request": 0.005, "limit": None},
    ],
)
@pytest.mark.parametrize(
    "memory",
    [
        {"request": 128974848, "limit": 128974848},
        {"request": 128.974848e6, "limit": 128.974848e6},
        {"request": "128.9748480M", "limit": "128.9748480M"},
        {"request": "128974848000m", "limit": "128974848000m"},
        {"request": "123Mi", "limit": "123Mi"},
        {"request": "128974848e0", "limit": "128974848e0"},
    ],
)
def test_resource_allocation_supported_formats(
    cpu: dict[str, Union[str, int, float, None]], memory: dict[str, Union[str, int, float, None]]
):
    allocations = ResourceAllocations(
        requests={ResourceType.CPU: cpu["request"], ResourceType.Memory: memory["request"]},
        limits={ResourceType.CPU: cpu["limit"], ResourceType.Memory: memory["limit"]},
    )
    assert allocations.requests[ResourceType.CPU] == 0.005
    assert allocations.limits[ResourceType.CPU] == None
    assert (allocations.requests[ResourceType.Memory] // 1) == 128974848.0
    assert (allocations.limits[ResourceType.Memory] // 1) == 128974848.0
