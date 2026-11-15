import pytest
from click.testing import Result
from typer.testing import CliRunner

from robusta_krr.core.models.allocations import RecommendationValue
from robusta_krr.core.models.result import ResourceScan
from robusta_krr.core.runner import has_recommendation_data
from robusta_krr.main import app, load_commands

runner = CliRunner(mix_stderr=False)
load_commands()


@pytest.mark.parametrize(
    "args, expected_exit_code",
    [
        (["--exclude-severity", "-f", "csv"], 0),
        (["--exclude-severity", "-f", "table"], 2),
        (["--exclude-severity"], 2),
    ],
)
def test_exclude_severity_option(args: list[str], expected_exit_code: int) -> None:
    result: Result = runner.invoke(app, ["simple", *args])
    assert result.exit_code == expected_exit_code


def test_hide_no_data_flag_is_registered() -> None:
    result: Result = runner.invoke(app, ["simple", "--help"])

    assert result.exit_code == 0, result.stdout
    assert "--hide-no-data" in result.stdout


def _make_scan(requests: dict[str, RecommendationValue], limits: dict[str, RecommendationValue]) -> ResourceScan:
    def recommendation(value: RecommendationValue) -> dict[str, object]:
        return {"value": value, "severity": "UNKNOWN"}

    return ResourceScan(
        object={
            "cluster": "mock-cluster",
            "name": "mock-object",
            "container": "mock-container",
            "pods": [],
            "hpa": None,
            "namespace": "default",
            "kind": "Deployment",
            "allocations": {
                "requests": {"cpu": "100m", "memory": "256Mi"},
                "limits": {"cpu": "200m", "memory": "512Mi"},
            },
            "labels": None,
            "annotations": None,
        },
        recommended={
            "requests": {resource: recommendation(value) for resource, value in requests.items()},
            "limits": {resource: recommendation(value) for resource, value in limits.items()},
            "info": {"cpu": "No data", "memory": "No data"},
        },
        severity="UNKNOWN",
    )


@pytest.mark.parametrize(
    "requests, limits, expected",
    [
        ({"cpu": "?", "memory": "?"}, {"cpu": "?", "memory": "?"}, False),
        ({"cpu": None, "memory": None}, {"cpu": None, "memory": None}, False),
        ({"cpu": 0.1, "memory": "?"}, {"cpu": "?", "memory": "?"}, True),
        ({"cpu": "?", "memory": "?"}, {"cpu": "?", "memory": 1024**2}, True),
    ],
)
def test_has_recommendation_data(
    requests: dict[str, RecommendationValue], limits: dict[str, RecommendationValue], expected: bool
) -> None:
    assert has_recommendation_data(_make_scan(requests, limits)) is expected

