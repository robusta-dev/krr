# This is an example on how to create your own custom formatter

from __future__ import annotations

from typing import Optional

import robusta_krr
from robusta_krr.api.models import ResourceType, Severity, register_severity_calculator


@register_severity_calculator(ResourceType.CPU)
def percentage_severity_calculator(
    current: Optional[float], recommended: Optional[float], resource_type: ResourceType
) -> Severity:
    """
    This is an example on how to create your own custom severity calculator
    You can use this decorator to bind a severity calculator function to a resource type.
    The function will be called with the current value, the recommended value and the resource type.
    The function should return a Severity enum value.

    If you have the same calculation for multiple resource types, you can use the `bind_calculator` decorator multiple times.
    Then, the function will be called for each resource type and you can use the resource type to distinguish between them.

    Keep in mind that you can not choose the strategy for the resource type using CLI - the last one created for the resource type will be used.
    """

    if current is None and recommended is None:
        return Severity.GOOD
    if current is None or recommended is None:
        return Severity.WARNING

    diff = abs(current - recommended) / current
    if diff >= 0.5:
        return Severity.CRITICAL
    elif diff >= 0.25:
        return Severity.WARNING
    elif diff >= 0.1:
        return Severity.OK
    else:
        return Severity.GOOD


# Running this file will register the formatter and make it available to the CLI
# Run it as `python ./custom_formatter.py simple --formater my_formatter`
if __name__ == "__main__":
    robusta_krr.run()
