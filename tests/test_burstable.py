import math

import numpy as np
import pytest
from unittest.mock import MagicMock
from typer.testing import CliRunner

from robusta_krr.main import app, load_commands
from robusta_krr.core.abstract.strategies import ResourceType
from robusta_krr.strategies.burstable import BurstableStrategy, BurstableStrategySettings

runner = CliRunner(mix_stderr=False)
load_commands()

# Pre-computed percentile values — these are what Prometheus returns after
# computing quantile_over_time on the server side.
CPU_REQUEST_VALUE = 0.3    # p50 CPU (cores)
CPU_LIMIT_VALUE   = 0.9    # p99 CPU (cores)
MEM_REQUEST_VALUE = 300e6  # p50 memory (bytes)
MEM_LIMIT_VALUE   = 800e6  # p90 memory (bytes)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_instant_data(value: float) -> dict:
    """Single-row instant-query result per pod: [[timestamp, value]]."""
    return {"pod-0": np.array([[0.0, float(value)]])}


def make_count_data(count: int) -> dict:
    return {"pod-0": np.array([[0.0, float(count)]])}


def make_history_data(
    cpu_request=CPU_REQUEST_VALUE,
    cpu_limit=CPU_LIMIT_VALUE,
    mem_request=MEM_REQUEST_VALUE,
    mem_limit=MEM_LIMIT_VALUE,
    count=200,
    oom_value=0,
):
    data = {
        "BurstableCPURequestLoader":    make_instant_data(cpu_request),
        "BurstableCPULimitLoader":      make_instant_data(cpu_limit),
        "BurstableMemoryRequestLoader": make_instant_data(mem_request),
        "BurstableMemoryLimitLoader":   make_instant_data(mem_limit),
        "CPUAmountLoader":              make_count_data(count),
        "MemoryAmountLoader":           make_count_data(count),
    }
    if oom_value > 0:
        data["MaxOOMKilledMemoryLoader"] = make_instant_data(oom_value)
    return data


def make_object_data(hpa=None):
    obj = MagicMock()
    obj.hpa = hpa
    return obj


def make_strategy(**kwargs):
    return BurstableStrategy(BurstableStrategySettings(**kwargs))


# ---------------------------------------------------------------------------
# CPU recommendation tests
# ---------------------------------------------------------------------------

def test_cpu_request_and_limit_use_separate_values():
    strategy = make_strategy()
    result = strategy.run(make_history_data(cpu_request=0.3, cpu_limit=0.9), make_object_data())

    cpu = result[ResourceType.CPU]
    assert cpu.request == pytest.approx(0.3)
    assert cpu.limit == pytest.approx(0.9)


def test_cpu_limit_is_none_when_disabled():
    strategy = make_strategy(disable_cpu_limit=True)
    result = strategy.run(make_history_data(), make_object_data())

    assert result[ResourceType.CPU].limit is None


def test_cpu_no_data_returns_undefined():
    strategy = make_strategy()
    history = make_history_data()
    history["BurstableCPURequestLoader"] = {}

    result = strategy.run(history, make_object_data())
    assert math.isnan(result[ResourceType.CPU].request)


def test_cpu_not_enough_data_returns_undefined():
    strategy = make_strategy(points_required=100)
    result = strategy.run(make_history_data(count=10), make_object_data())

    assert math.isnan(result[ResourceType.CPU].request)


def test_cpu_hpa_returns_undefined_by_default():
    hpa = MagicMock()
    hpa.target_cpu_utilization_percentage = 80
    strategy = make_strategy(allow_hpa=False)
    result = strategy.run(make_history_data(), make_object_data(hpa=hpa))

    assert math.isnan(result[ResourceType.CPU].request)


def test_cpu_hpa_allowed_when_flag_set():
    hpa = MagicMock()
    hpa.target_cpu_utilization_percentage = 80
    strategy = make_strategy(allow_hpa=True)
    result = strategy.run(make_history_data(), make_object_data(hpa=hpa))

    assert not math.isnan(result[ResourceType.CPU].request)


# ---------------------------------------------------------------------------
# Memory recommendation tests
# ---------------------------------------------------------------------------

def test_memory_request_has_no_buffer():
    strategy = make_strategy(memory_buffer_percentage=15)
    result = strategy.run(make_history_data(mem_request=300e6), make_object_data())

    assert result[ResourceType.Memory].request == pytest.approx(300e6)


def test_memory_limit_applies_buffer():
    strategy = make_strategy(memory_buffer_percentage=15)
    result = strategy.run(make_history_data(mem_limit=800e6), make_object_data())

    assert result[ResourceType.Memory].limit == pytest.approx(800e6 * 1.15)


def test_memory_limit_higher_than_request():
    strategy = make_strategy(memory_buffer_percentage=15)
    result = strategy.run(make_history_data(mem_request=300e6, mem_limit=800e6), make_object_data())

    mem = result[ResourceType.Memory]
    assert mem.limit > mem.request


def test_oom_kill_bumps_limit_not_request():
    oom_value = 3000e6  # larger than mem_limit * buffer → drives the limit
    strategy = make_strategy(
        use_oomkill_data=True,
        oom_memory_buffer_percentage=25,
        memory_buffer_percentage=15,
    )
    history = make_history_data(mem_request=300e6, mem_limit=800e6, oom_value=oom_value)
    result = strategy.run(history, make_object_data())

    mem = result[ResourceType.Memory]
    assert mem.request == pytest.approx(300e6)
    assert mem.limit == pytest.approx(oom_value * 1.25)


def test_oom_kill_not_used_when_smaller_than_normal_limit():
    oom_value = 1.0  # negligibly small → normal limit wins
    strategy = make_strategy(
        use_oomkill_data=True,
        oom_memory_buffer_percentage=25,
        memory_buffer_percentage=15,
    )
    history = make_history_data(mem_limit=800e6, oom_value=oom_value)
    result = strategy.run(history, make_object_data())

    assert result[ResourceType.Memory].limit == pytest.approx(800e6 * 1.15)


def test_memory_no_data_returns_undefined():
    strategy = make_strategy()
    history = make_history_data()
    history["BurstableMemoryRequestLoader"] = {}

    result = strategy.run(history, make_object_data())
    assert math.isnan(result[ResourceType.Memory].request)


def test_memory_not_enough_data_returns_undefined():
    strategy = make_strategy(points_required=100)
    result = strategy.run(make_history_data(count=10), make_object_data())

    assert math.isnan(result[ResourceType.Memory].request)


def test_memory_hpa_returns_undefined_by_default():
    hpa = MagicMock()
    hpa.target_cpu_utilization_percentage = None
    hpa.target_memory_utilization_percentage = 80
    strategy = make_strategy(allow_hpa=False)
    result = strategy.run(make_history_data(), make_object_data(hpa=hpa))

    assert math.isnan(result[ResourceType.Memory].request)


# ---------------------------------------------------------------------------
# CLI smoke tests
# ---------------------------------------------------------------------------

def test_burstable_help():
    result = runner.invoke(app, ["burstable", "--help"])
    try:
        assert result.exit_code == 0
    except AssertionError as e:
        raise e from result.exception


def test_burstable_settings_exposes_all_expected_fields():
    expected = {
        "cpu_requests_percentile",
        "cpu_limits_percentile",
        "memory_requests_percentile",
        "memory_limits_percentile",
        "memory_buffer_percentage",
        "disable_cpu_limit",
        "points_required",
        "allow_hpa",
        "use_oomkill_data",
        "oom_memory_buffer_percentage",
    }
    assert expected.issubset(set(BurstableStrategySettings.__fields__.keys()))
