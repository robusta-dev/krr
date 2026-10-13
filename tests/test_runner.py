import logging
from unittest.mock import MagicMock

import pytest
from click.testing import Result
from typer.testing import CliRunner

from robusta_krr.core import runner as runner_module
from robusta_krr.core.runner import Runner
from robusta_krr.main import app, load_commands

EXPECTED_AMP_HISTORY_LIMIT_HOURS = 95 * 24

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


@pytest.mark.parametrize(
    ("history_duration", "expected_history_duration", "expects_warning"),
    [
        (
            EXPECTED_AMP_HISTORY_LIMIT_HOURS - 1,
            EXPECTED_AMP_HISTORY_LIMIT_HOURS - 1,
            False,
        ),
        (EXPECTED_AMP_HISTORY_LIMIT_HOURS, EXPECTED_AMP_HISTORY_LIMIT_HOURS, False),
        (
            EXPECTED_AMP_HISTORY_LIMIT_HOURS + 1,
            EXPECTED_AMP_HISTORY_LIMIT_HOURS,
            True,
        ),
    ],
    ids=["below", "at", "above"],
)
def test_adjust_amp_history_duration_limit(
    monkeypatch, caplog, history_duration, expected_history_duration, expects_warning
) -> None:
    monkeypatch.setattr(runner_module, "settings", MagicMock(eks_managed_prom=True))
    runner_instance = Runner.__new__(Runner)
    runner_instance._strategy = MagicMock()
    runner_instance._strategy.settings.history_duration = history_duration
    runner_instance._strategy.settings.timeframe_duration = 30

    with caplog.at_level(logging.WARNING, logger="krr"):
        runner_instance._adjust_amp_query_limits()

    assert runner_instance._strategy.settings.history_duration == expected_history_duration
    assert ("history duration exceeds" in caplog.text) is expects_warning
