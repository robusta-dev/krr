import pytest
from click.testing import Result
from typer.testing import CliRunner

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


@pytest.mark.parametrize("threshold", ["good", "WARNING", "critical"])
def test_severity_threshold_option(threshold: str) -> None:
    result: Result = runner.invoke(app, ["simple", "-q", "--severity-threshold", threshold])
    try:
        assert result.exit_code == 0, result.stdout
    except AssertionError as e:
        raise e from result.exception


def test_severity_threshold_rejects_unknown_value() -> None:
    result: Result = runner.invoke(app, ["simple", "-q", "--severity-threshold", "nope"])
    assert result.exit_code == 2
