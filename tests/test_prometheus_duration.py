from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from robusta_krr.core.integrations.prometheus.metrics.base import PrometheusMetric
from robusta_krr.core.integrations.prometheus.metrics.cpu import PercentileCPULoader
from robusta_krr.core.integrations.prometheus.metrics.memory import MaxMemoryLoader


@pytest.mark.parametrize("hours", [1, 24, 25, 36, 47, 48])
def test_duration_preserves_full_history(hours):
    duration = timedelta(hours=hours)
    assert PrometheusMetric._step_to_string(None, duration) == f"{hours * 3600}s"


@pytest.mark.parametrize("seconds", [30, 90, 86430])
def test_duration_preserves_seconds(seconds):
    assert PrometheusMetric._step_to_string(None, timedelta(seconds=seconds)) == f"{seconds}s"


@pytest.mark.asyncio
@pytest.mark.parametrize("loader_type", [MaxMemoryLoader, PercentileCPULoader(99)])
async def test_load_data_uses_full_36_hour_query_window(loader_type):
    loader = loader_type(prometheus=None, service_name="test")
    loader.query_prometheus = AsyncMock(return_value=[])
    obj = SimpleNamespace(
        namespace="default", container="app", pods=[SimpleNamespace(name="app-1")], pods_count=1
    )

    await loader.load_data(obj, timedelta(hours=36), timedelta(minutes=1))

    data = loader.query_prometheus.call_args.args[0]
    assert "[129600s:60s]" in data.query
    assert data.end_time - data.start_time == timedelta(hours=36)
