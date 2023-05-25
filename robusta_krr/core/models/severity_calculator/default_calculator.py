from __future__ import annotations

from typing import Optional

from robusta_krr.core.models.severity import Severity
from robusta_krr.core.models.severity_calculator.base_calculator import BaseSeverityCalculator


class DefaultSeverityCalculator(BaseSeverityCalculator):
    def calculate(self, current: Optional[float], recommended: Optional[float]) -> Severity:
        return Severity.UNKNOWN
