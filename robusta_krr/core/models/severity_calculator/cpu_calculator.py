from __future__ import annotations

from typing import Optional

from robusta_krr.core.models.allocations import ResourceType
from robusta_krr.core.models.severity import Severity
from robusta_krr.core.models.severity_calculator.base_calculator import BaseSeverityCalculator, bind_calculator


@bind_calculator(ResourceType.CPU)
class CPUSeverityCalculator(BaseSeverityCalculator):
    def calculate(self, current: Optional[float], recommended: Optional[float]) -> Severity:
        if current is None and recommended is None:
            return Severity.GOOD
        if current is None or recommended is None:
            return Severity.WARNING

        diff = abs(current - recommended)

        if diff >= 0.5:
            return Severity.CRITICAL
        elif diff >= 0.25:
            return Severity.WARNING
        elif diff >= 0.1:
            return Severity.OK
        else:
            return Severity.GOOD
