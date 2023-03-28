"""
    Test the krr command line interface and a general execution.
    Requires a running kubernetes cluster with the kubectl command configured.
"""

import json

import pytest
import yaml
from typer.testing import CliRunner

from robusta_krr import app

runner = CliRunner()

STRATEGY_NAME = "simple"


def test_help():
    result = runner.invoke(app, [STRATEGY_NAME, "--help"])
    assert result.exit_code == 0


@pytest.mark.parametrize("log_flag", ["-v", "-q"])
def test_run(log_flag: str):
    result = runner.invoke(app, [STRATEGY_NAME, log_flag, "--namespace", "default"])
    assert result.exit_code == 0


@pytest.mark.parametrize("format", ["json", "yaml", "table", "pprint"])
def test_output_json(format: str):
    result = runner.invoke(app, [STRATEGY_NAME, "-q", "-f", format, "--namespace", "default"])
    assert result.exit_code == 0

    if format == "json":
        assert json.loads(result.stdout)

    if format == "yaml":
        assert yaml.safe_load(result.stdout)
