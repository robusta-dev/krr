from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from robusta_krr.core.integrations.prometheus.metrics_service import prometheus_metrics_service
from robusta_krr.core.integrations.prometheus.metrics_service.prometheus_metrics_service import PrometheusMetricsService

EXPECTED_AMP_RANGE_QUERY_THRESHOLD = timedelta(days=32)
EXPECTED_AMP_RANGE_QUERY_LIMIT = timedelta(days=95)
EXPECTED_AMP_RANGE_QUERY_STEP = timedelta(hours=1)
EXPECTED_AMP_RANGE_QUERY_STEP_LITERAL = f"{int(EXPECTED_AMP_RANGE_QUERY_STEP.total_seconds())}s"
LONG_HISTORY_PERIOD = timedelta(days=40)
EXPECTED_MAX_INSTANT_QUERY_PERIOD_LITERAL = "32d"
TEST_PROMETHEUS_QUERY = "example_metric{}"


@pytest.fixture
def metrics_service() -> PrometheusMetricsService:
    service = PrometheusMetricsService.__new__(PrometheusMetricsService)
    service.query = AsyncMock()
    service.query_range = AsyncMock()
    service.get_prometheus_cluster_label = MagicMock(return_value="")
    return service


@pytest.fixture
def configure_amp(monkeypatch):
    def configure(enabled: bool) -> None:
        monkeypatch.setattr(prometheus_metrics_service, "settings", MagicMock(eks_managed_prom=enabled))

    return configure


@pytest.mark.asyncio
async def test_load_pods_uses_range_queries_for_long_amp_history(configure_amp, metrics_service):
    configure_amp(True)
    metrics_service.query_range.side_effect = [
        [{"metric": {"replicaset": "example-abc"}}],
        [{"metric": {"pod": "example-abc-123"}}],
    ]
    metrics_service.query.return_value = [{"metric": {"pod": "example-abc-123"}}]
    workload = MagicMock(kind="Deployment", name="example", namespace="default")

    pods = await metrics_service.load_pods(workload, LONG_HISTORY_PERIOD)

    assert [pod.name for pod in pods] == ["example-abc-123"]
    assert pods[0].deleted is False
    assert metrics_service.query_range.await_count == 2
    for call in metrics_service.query_range.await_args_list:
        assert "last_over_time(" in call.args[0]
        assert f"[{EXPECTED_AMP_RANGE_QUERY_STEP_LITERAL}]" in call.args[0]
        assert f"[{EXPECTED_MAX_INSTANT_QUERY_PERIOD_LITERAL}]" not in call.args[0]
        assert call.kwargs["end"] - call.kwargs["start"] == LONG_HISTORY_PERIOD - EXPECTED_AMP_RANGE_QUERY_STEP
        assert call.kwargs["step"] == EXPECTED_AMP_RANGE_QUERY_STEP


@pytest.mark.asyncio
async def test_load_pods_keeps_instant_queries_below_amp_limit(configure_amp, metrics_service):
    configure_amp(True)
    metrics_service.query.side_effect = [
        [{"metric": {"replicaset": "example-abc"}}],
        [{"metric": {"pod": "example-abc-123"}}],
        [{"metric": {"pod": "example-abc-123"}}],
    ]
    workload = MagicMock(kind="Deployment", name="example", namespace="default")

    await metrics_service.load_pods(workload, timedelta(days=31))

    metrics_service.query_range.assert_not_awaited()
    historical_queries = [call.args[0] for call in metrics_service.query.await_args_list[:2]]
    assert "[31d]" in historical_queries[0]
    assert "last_over_time(" in historical_queries[1]
    assert "[31d]" in historical_queries[1]


@pytest.mark.asyncio
async def test_load_pods_keeps_instant_queries_for_non_amp(configure_amp, metrics_service):
    configure_amp(False)
    metrics_service.query.side_effect = [
        [{"metric": {"replicaset": "example-abc"}}],
        [{"metric": {"pod": "example-abc-123"}}],
        [{"metric": {"pod": "example-abc-123"}}],
    ]
    workload = MagicMock(kind="Deployment", name="example", namespace="default")

    await metrics_service.load_pods(workload, LONG_HISTORY_PERIOD)

    metrics_service.query_range.assert_not_awaited()
    historical_queries = [call.args[0] for call in metrics_service.query.await_args_list[:2]]
    assert f"[{EXPECTED_MAX_INSTANT_QUERY_PERIOD_LITERAL}]" in historical_queries[0]
    assert "last_over_time(" in historical_queries[1]
    assert f"[{EXPECTED_MAX_INSTANT_QUERY_PERIOD_LITERAL}]" in historical_queries[1]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("period", "expected_covered_period"),
    [
        (LONG_HISTORY_PERIOD, LONG_HISTORY_PERIOD),
        (LONG_HISTORY_PERIOD + timedelta.resolution, LONG_HISTORY_PERIOD + EXPECTED_AMP_RANGE_QUERY_STEP),
        (
            LONG_HISTORY_PERIOD + EXPECTED_AMP_RANGE_QUERY_STEP - timedelta.resolution,
            LONG_HISTORY_PERIOD + EXPECTED_AMP_RANGE_QUERY_STEP,
        ),
        (
            LONG_HISTORY_PERIOD + EXPECTED_AMP_RANGE_QUERY_STEP,
            LONG_HISTORY_PERIOD + EXPECTED_AMP_RANGE_QUERY_STEP,
        ),
    ],
    ids=["exact", "just-above", "just-below-next-step", "next-step"],
)
async def test_range_query_covers_fractional_history_duration(
    configure_amp, metrics_service, period, expected_covered_period
):
    configure_amp(True)
    metrics_service.query_range.return_value = []

    await metrics_service._query_historical_series(
        TEST_PROMETHEUS_QUERY, period, EXPECTED_MAX_INSTANT_QUERY_PERIOD_LITERAL
    )

    call = metrics_service.query_range.await_args
    start = call.kwargs["start"]
    end = call.kwargs["end"]
    step = call.kwargs["step"]
    assert (end - start) % step == timedelta(0)
    assert end - start + step == expected_covered_period


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("period", "uses_range_query"),
    [
        (EXPECTED_AMP_RANGE_QUERY_THRESHOLD - timedelta.resolution, False),
        (EXPECTED_AMP_RANGE_QUERY_THRESHOLD, True),
        (EXPECTED_AMP_RANGE_QUERY_THRESHOLD + timedelta.resolution, True),
    ],
    ids=["below", "at", "above"],
)
async def test_amp_query_type_boundary(configure_amp, metrics_service, period, uses_range_query):
    configure_amp(True)
    metrics_service.query.return_value = []
    metrics_service.query_range.return_value = []

    await metrics_service._query_historical_series(TEST_PROMETHEUS_QUERY, period, "31d")

    if uses_range_query:
        metrics_service.query_range.assert_awaited_once()
        metrics_service.query.assert_not_awaited()
    else:
        metrics_service.query.assert_awaited_once()
        metrics_service.query_range.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("period", "expected_period"),
    [
        (
            EXPECTED_AMP_RANGE_QUERY_LIMIT - EXPECTED_AMP_RANGE_QUERY_STEP,
            EXPECTED_AMP_RANGE_QUERY_LIMIT - EXPECTED_AMP_RANGE_QUERY_STEP,
        ),
        (EXPECTED_AMP_RANGE_QUERY_LIMIT, EXPECTED_AMP_RANGE_QUERY_LIMIT),
        (
            EXPECTED_AMP_RANGE_QUERY_LIMIT + EXPECTED_AMP_RANGE_QUERY_STEP,
            EXPECTED_AMP_RANGE_QUERY_LIMIT,
        ),
    ],
    ids=["below", "at", "above"],
)
async def test_amp_query_range_limit_boundary(configure_amp, metrics_service, period, expected_period):
    configure_amp(True)
    metrics_service.query_range.return_value = []

    await metrics_service._query_historical_series(
        TEST_PROMETHEUS_QUERY, period, EXPECTED_MAX_INSTANT_QUERY_PERIOD_LITERAL
    )

    call = metrics_service.query_range.await_args
    start = call.kwargs["start"]
    end = call.kwargs["end"]
    step = call.kwargs["step"]
    assert end - start + step == expected_period


@pytest.mark.asyncio
async def test_query_range_uses_total_step_seconds():
    service = PrometheusMetricsService.__new__(PrometheusMetricsService)
    service.executor = None
    prometheus = MagicMock()
    prometheus.safe_custom_query_range.return_value = {"result": []}
    service.get_prometheus = MagicMock(return_value=prometheus)
    now = datetime.now()

    await service.query_range(TEST_PROMETHEUS_QUERY, now - timedelta(days=1), now, timedelta(days=1))

    assert prometheus.safe_custom_query_range.call_args.kwargs["step"] == "86400s"
