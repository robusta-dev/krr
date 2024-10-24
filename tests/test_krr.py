import pytest
from typing import Literal, Union
from unittest.mock import patch, Mock, MagicMock
from typer.testing import CliRunner

from robusta_krr.main import app, load_commands
from robusta_krr.core.integrations.kubernetes import ClusterLoader
from robusta_krr.core.models.config import settings

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

@pytest.mark.parametrize(
        "setting_namespaces,cluster_all_ns,expected",[
            (
                # default settings
                "*",
                ["kube-system", "robusta-frontend", "robusta-backend", "infra-grafana"],
                "*"
            ),
            (
                # list of namespace provided from arguments without regex pattern
                ["robusta-krr", "kube-system"],
                ["kube-system", "robusta-frontend", "robusta-backend", "robusta-krr"],
                ["robusta-krr", "kube-system"]
            ),
            (
                # list of namespace provided from arguments with regex pattern and will not duplicating in final result
                ["robusta-.*", "robusta-frontend"],
                ["kube-system", "robusta-frontend", "robusta-backend", "robusta-krr"],
                ["robusta-frontend", "robusta-backend", "robusta-krr"]
            ),
            (
                # namespace provided with regex pattern and will match for some namespaces
                [".*end$"],
                ["kube-system", "robusta-frontend", "robusta-backend", "robusta-krr"],
                ["robusta-frontend", "robusta-backend"]
            )
        ]
    )
def test_cluster_namespace_list(
        setting_namespaces: Union[Literal["*"], list[str]],
        cluster_all_ns: list[str],
        expected: Union[Literal["*"], list[str]],
    ):
    cluster = ClusterLoader()
    with patch("robusta_krr.core.models.config.settings.namespaces", setting_namespaces):
        with patch.object(cluster.core, "list_namespace", return_value=MagicMock(
            items=[MagicMock(**{"metadata.name": m}) for m in cluster_all_ns])):
            assert sorted(cluster.namespaces) == sorted(expected)
