from types import SimpleNamespace

import pytest

from robusta_krr.core.models.result import filter_scans_by_severity
from robusta_krr.core.models.severity import Severity


@pytest.mark.parametrize(
    "severity, threshold, expected",
    [
        (Severity.CRITICAL, Severity.WARNING, True),
        (Severity.WARNING, Severity.WARNING, True),
        (Severity.OK, Severity.WARNING, False),
        (Severity.GOOD, Severity.WARNING, False),
        (Severity.GOOD, Severity.GOOD, True),
        # UNKNOWN cannot be measured, so it is never dropped
        (Severity.UNKNOWN, Severity.CRITICAL, True),
        # an UNKNOWN threshold keeps everything
        (Severity.GOOD, Severity.UNKNOWN, True),
    ],
)
def test_is_at_least(severity: Severity, threshold: Severity, expected: bool) -> None:
    assert severity.is_at_least(threshold) is expected


def test_filter_scans_by_severity_no_threshold() -> None:
    scans = [SimpleNamespace(severity=s) for s in Severity]
    assert filter_scans_by_severity(scans, None) == scans


def test_filter_scans_by_severity_warning() -> None:
    scans = [
        SimpleNamespace(severity=s) for s in [Severity.GOOD, Severity.WARNING, Severity.CRITICAL, Severity.UNKNOWN]
    ]
    kept = [scan.severity for scan in filter_scans_by_severity(scans, Severity.WARNING)]
    # GOOD is dropped, order is otherwise preserved, UNKNOWN is always kept
    assert kept == [Severity.WARNING, Severity.CRITICAL, Severity.UNKNOWN]
