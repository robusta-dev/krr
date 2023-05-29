import json

import pytest
import yaml
from typer.testing import CliRunner

from robusta_krr.main import app, load_commands

runner = CliRunner()
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
def test_output_formats(format: str):
    result = runner.invoke(app, [STRATEGY_NAME, "-q", "-f", format])
    try:
        assert result.exit_code == 0, result.exc_info
    except AssertionError as e:
        raise e from result.exception

    try:
        if format == "json":
            json_output = json.loads(result.stdout)
            assert json_output, result.stdout
            assert len(json_output["scans"]) > 0, result.stdout

        if format == "yaml":
            assert yaml.safe_load(result.stdout), result.stdout
    except Exception as e:
        raise Exception(result.stdout) from e
