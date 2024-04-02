import pytest
from typer.testing import CliRunner

from robusta_krr.main import app, load_commands

runner = CliRunner(mix_stderr=False)
load_commands()

STRATEGY_NAME = "simple"


def test_help():
    result = runner.invoke(app, [STRATEGY_NAME, "--help"])
    try:
        assert result.exit_code == 0
    except AssertionError as e:
        raise e from result.exception


@pytest.mark.parametrize("log_flag", ["-v", "-q"])
def test_run(log_flag: str):
    result = runner.invoke(app, [STRATEGY_NAME, log_flag, "--namespace", "default"])
    try:
        assert result.exit_code == 0, result.stdout
    except AssertionError as e:
        raise e from result.exception


@pytest.mark.parametrize("format", ["json", "yaml", "table", "pprint"])
@pytest.mark.parametrize("output", ["--logtostderr", "-q"])
def test_output_formats(format: str, output: str):
    result = runner.invoke(app, [STRATEGY_NAME, output, "-f", format])
    try:
        assert result.exit_code == 0, result.exc_info
    except AssertionError as e:
        raise e from result.exception
