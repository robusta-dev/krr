"""
Tests for the Kubernetes state metrics dialects and for pod owner resolution.

The kube-state-metrics expectations are golden copies of the queries KRR sent
before dialects existed, so any accidental change to the default behaviour
fails here.
"""

import asyncio
import re
from datetime import timedelta

import pytest

from robusta_krr.core.integrations.prometheus.metrics import MaxOOMKilledMemoryLoader
from robusta_krr.core.integrations.prometheus.metrics_service.prometheus_metrics_service import PrometheusMetricsService
from robusta_krr.core.models.allocations import ResourceAllocations
from robusta_krr.core.models.config import Config
from robusta_krr.core.models.metric_dialects import (
    KSM_DIALECT,
    OTEL_DIALECT,
    MetricDialectName,
    OwnerResolutionName,
    get_dialect,
)
from robusta_krr.core.models.objects import K8sObjectData, PodData

RECORDING_RULE = "namespace_workload_pod:kube_pod_owner:relabel"
OTEL_PROBE = 'k8s_pod_phase{namespace!=""}'


def normalized(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def make_object(kind: str = "Deployment") -> K8sObjectData:
    return K8sObjectData(
        cluster="mock-cluster",
        name="mock-object-1",
        container="mock-container-1",
        pods=[PodData(name="mock-pod-1", deleted=False), PodData(name="mock-pod-2", deleted=False)],
        namespace="default",
        kind=kind,
        allocations=ResourceAllocations(
            requests={"cpu": 1, "memory": 1},  # type: ignore
            limits={"cpu": 2, "memory": 2},  # type: ignore
        ),
    )


@pytest.fixture
def configure():
    def _configure(**kwargs) -> None:
        Config.set_config(
            Config(
                format="table",
                show_cluster_name=False,
                strategy="simple",
                log_to_stderr=False,
                other_args={},
                # NOTE: Config validates its defaults, and the "*" default of
                # `resources` is only accepted when it comes from the CLI.
                resources=["Deployment"],
                **kwargs,
            )
        )

    _configure()
    return _configure


PROBE_RE = re.compile(r"count\(last_over_time\((?P<metric>[^{]+)\{(?P<matchers>.*)\}\[\w+\]\)\)")


class FakePrometheusMetricsService(PrometheusMetricsService):
    """
    A PrometheusMetricsService that records queries instead of sending them.

    `existing_metrics` holds what this Prometheus would answer a detection probe
    with, spelled exactly as the probe asks for it: `"kube_pod_status_phase"` for
    a probe without a selector and `'k8s_pod_phase{namespace!=""}'` for one with.
    A metric that exists under unmapped labels is therefore expressed by listing
    it without the selector.
    """

    def __init__(self, *, existing_metrics: tuple[str, ...] = (), responses: list | None = None) -> None:
        self.cluster = "mock-cluster"
        self.api_client = None
        self.executor = None
        self._dialect = None
        self._dialect_lock = asyncio.Lock()
        self._owner_resolution = None
        self._owner_resolution_lock = asyncio.Lock()

        self.prometheus = None
        self.existing_metrics = set(existing_metrics)
        self.responses = responses if responses is not None else []
        self.queries: list[str] = []

    def get_prometheus(self):
        return self.prometheus

    async def query(self, query: str) -> list:
        self.queries.append(query)

        probe = PROBE_RE.fullmatch(normalized(query))
        if probe:
            return [{"metric": {}, "value": [0, "1"]}] if self._probe_key(probe) in self.existing_metrics else []

        if self.responses:
            return self.responses.pop(0)
        return [{"metric": {}, "value": [0, "1"]}]

    def _probe_key(self, probe: re.Match) -> str:
        metric = probe.group("metric")
        # The cluster label is orthogonal to what a probe is asking about.
        selector = probe.group("matchers").replace(normalized(self._single_cluster_label()), "").strip(" ,")
        return f"{metric}{{{selector}}}" if selector else metric

    @property
    def data_queries(self) -> list[str]:
        """Queries that are not dialect detection probes."""

        return [query for query in self.queries if not normalized(query).startswith("count(")]


# --------------------- Query building --------------------- #


def test_oom_killed_query_with_kube_state_metrics(configure):
    query = MaxOOMKilledMemoryLoader(prometheus=None, service_name="Prometheus", dialect=KSM_DIALECT).get_query(
        make_object(), "1d", "30m"
    )

    assert normalized(query) == normalized("""
        max_over_time(
            max(
                max(
                    kube_pod_container_resource_limits{
                        resource="memory", namespace="default",
                        pod=~"mock-pod-1|mock-pod-2",
                        container="mock-container-1"
                    }
                ) by (pod, container, job)
                * on(pod, container, job) group_left(reason)
                max(
                    kube_pod_container_status_last_terminated_reason{
                        reason="OOMKilled",
                        namespace="default",
                        pod=~"mock-pod-1|mock-pod-2",
                        container="mock-container-1"
                    }
                ) by (pod, container, job, reason)
            ) by (container, pod, job)
            [1d:30m]
        )
        """)


def test_oom_killed_query_with_otel(configure):
    query = MaxOOMKilledMemoryLoader(prometheus=None, service_name="Prometheus", dialect=OTEL_DIALECT).get_query(
        make_object(), "1d", "30m"
    )

    assert normalized(query) == normalized("""
        max_over_time(
            max(
                max(
                    k8s_container_memory_limit_bytes{
                        namespace="default",
                        pod=~"mock-pod-1|mock-pod-2",
                        container="mock-container-1"
                    }
                ) by (pod, container, job)
                * on(pod, container, job) group_left(k8s_container_status_reason)
                max(
                    k8s_container_status_reason{
                        k8s_container_status_reason="OOMKilled",
                        namespace="default",
                        pod=~"mock-pod-1|mock-pod-2",
                        container="mock-container-1"
                    }
                ) by (pod, container, job, k8s_container_status_reason)
            ) by (container, pod, job)
            [1d:30m]
        )
        """)


def test_dialect_defaults_to_kube_state_metrics(configure):
    loader = MaxOOMKilledMemoryLoader(prometheus=None, service_name="Prometheus")

    assert loader.dialect == KSM_DIALECT


@pytest.mark.asyncio
async def test_gather_data_passes_the_detected_dialect_to_the_loader(configure):
    service = FakePrometheusMetricsService(existing_metrics=(OTEL_PROBE,))
    seen = {}

    class RecordingLoader(MaxOOMKilledMemoryLoader):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            seen["dialect"] = self.dialect

        async def load_data(self, object, period, step):
            return {}

    await service.gather_data(make_object(), RecordingLoader, timedelta(days=1))

    assert seen["dialect"] == OTEL_DIALECT


@pytest.mark.asyncio
async def test_cluster_summary_queries_with_kube_state_metrics(configure):
    service = FakePrometheusMetricsService(existing_metrics=("kube_pod_status_phase",))

    await service.get_cluster_summary()

    assert [normalized(query) for query in service.data_queries] == [
        'sum(max by (node) (kube_node_status_capacity{ resource="memory" }))',
        'sum(max by (node) (kube_node_status_capacity{ resource="cpu" }))',
        'sum(max(kube_pod_container_resource_requests{ resource="memory", namespace="kube-system" }) '
        "by (job, pod, container) )",
        'sum(max(kube_pod_container_resource_requests{ resource="cpu", namespace="kube-system" }) '
        "by (job, pod, container) )",
    ]


@pytest.mark.asyncio
async def test_cluster_summary_queries_with_otel(configure):
    service = FakePrometheusMetricsService(existing_metrics=(OTEL_PROBE,))

    await service.get_cluster_summary()

    assert [normalized(query) for query in service.data_queries] == [
        "sum(max by (host_name) (system_memory_limit_bytes{ }))",
        "sum(max by (host_name) (system_cpu_logical_count{ }))",
        'sum(max(k8s_container_memory_request_bytes{ namespace="kube-system" }) by (job, pod, container) )',
        'sum(max(k8s_container_cpu_request{ namespace="kube-system" }) by (job, pod, container) )',
    ]


@pytest.mark.asyncio
async def test_cluster_summary_keeps_the_cluster_label(configure):
    configure(
        prometheus_metrics_dialect=MetricDialectName.KUBE_STATE_METRICS,
        prometheus_label="cluster",
        prometheus_cluster_label="prod",
    )
    service = FakePrometheusMetricsService()

    await service.get_cluster_summary()

    queries = [normalized(query) for query in service.data_queries]
    assert queries[0] == 'sum(max by (node) (kube_node_status_capacity{ resource="memory", cluster="prod" }))'
    assert queries[2] == (
        'sum(max(kube_pod_container_resource_requests{ resource="memory", namespace="kube-system" , '
        'cluster="prod" }) by (job, pod, container) )'
    )


# --------------------- Dialect detection --------------------- #


@pytest.mark.asyncio
async def test_detection_prefers_kube_state_metrics(configure):
    service = FakePrometheusMetricsService(existing_metrics=("kube_pod_status_phase", OTEL_PROBE))

    assert await service.get_dialect() == KSM_DIALECT


@pytest.mark.asyncio
async def test_detection_falls_back_to_otel(configure):
    service = FakePrometheusMetricsService(existing_metrics=(OTEL_PROBE,))

    assert await service.get_dialect() == OTEL_DIALECT


@pytest.mark.asyncio
async def test_detection_defaults_to_kube_state_metrics_when_nothing_matches(configure):
    service = FakePrometheusMetricsService()

    assert await service.get_dialect() == KSM_DIALECT


@pytest.mark.asyncio
async def test_otel_is_rejected_when_the_labels_are_not_mapped(configure, caplog):
    # k8s_pod_phase exists, but the Collector left the Kubernetes resource
    # attributes as k8s_namespace_name etc. instead of mapping them to namespace.
    service = FakePrometheusMetricsService(existing_metrics=("k8s_pod_phase",))

    assert await service.get_dialect() == KSM_DIALECT
    assert "k8s_pod_phase exists but has no" in caplog.text


@pytest.mark.asyncio
async def test_probes_use_a_lookback_window(configure):
    # An instant vector would report a metric as absent after a scrape gap, and
    # detection would silently switch dialects for the whole scan.
    service = FakePrometheusMetricsService(existing_metrics=(OTEL_PROBE,))

    await service.get_dialect()

    assert all("last_over_time" in query for query in service.queries)
    assert service.queries != []


@pytest.mark.asyncio
async def test_detection_is_cached(configure):
    service = FakePrometheusMetricsService(existing_metrics=(OTEL_PROBE,))

    await service.get_dialect()
    probe_count = len(service.queries)
    await service.get_dialect()

    assert len(service.queries) == probe_count


@pytest.mark.asyncio
async def test_explicit_dialect_is_not_probed(configure):
    configure(prometheus_metrics_dialect=MetricDialectName.OTEL)
    service = FakePrometheusMetricsService(existing_metrics=("kube_pod_status_phase",))

    assert await service.get_dialect() == OTEL_DIALECT
    assert service.queries == []


def test_get_dialect_rejects_auto():
    with pytest.raises(ValueError):
        get_dialect(MetricDialectName.AUTO)


# --------------------- Owner resolution --------------------- #


@pytest.mark.asyncio
async def test_owner_resolution_prefers_owner_metrics(configure):
    service = FakePrometheusMetricsService(existing_metrics=("kube_pod_owner", RECORDING_RULE))

    assert await service.get_owner_resolution() == OwnerResolutionName.KUBE_STATE_METRICS


@pytest.mark.asyncio
async def test_owner_resolution_falls_back_to_recording_rule(configure):
    service = FakePrometheusMetricsService(existing_metrics=(RECORDING_RULE,))

    assert await service.get_owner_resolution() == OwnerResolutionName.RECORDING_RULE


@pytest.mark.asyncio
async def test_owner_resolution_defaults_to_owner_metrics(configure, caplog):
    service = FakePrometheusMetricsService()

    assert await service.get_owner_resolution() == OwnerResolutionName.KUBE_STATE_METRICS
    # Neither source has data, so pod lists will be empty. Say so.
    assert "Neither kube_pod_owner nor" in caplog.text


@pytest.mark.asyncio
async def test_load_pods_with_owner_metrics(configure):
    configure(
        prometheus_metrics_dialect=MetricDialectName.KUBE_STATE_METRICS,
        prometheus_owner_resolution=OwnerResolutionName.KUBE_STATE_METRICS,
    )
    service = FakePrometheusMetricsService(
        responses=[
            [{"metric": {"replicaset": "mock-object-1-abc"}}],
            [{"metric": {"pod": "mock-pod-1"}}, {"metric": {"pod": "mock-pod-2"}}],
            [{"metric": {"pod": "mock-pod-1"}}],
        ]
    )

    pods = await service.load_pods(make_object(), timedelta(days=1))

    assert sorted((pod.name, pod.deleted) for pod in pods) == [("mock-pod-1", False), ("mock-pod-2", True)]
    queries = [normalized(query) for query in service.data_queries]
    assert queries[0] == (
        'kube_replicaset_owner{ owner_name="mock-object-1", owner_kind="Deployment", namespace="default" }[24h]'
    )
    assert queries[1] == (
        'last_over_time( kube_pod_owner{ owner_name=~"mock-object-1-abc", owner_kind="ReplicaSet", '
        'namespace="default" }[24h] )'
    )
    assert queries[2] == (
        'kube_pod_status_phase{ phase="Running", pod=~"mock-pod-1|mock-pod-2", namespace="default" } == 1'
    )


@pytest.mark.asyncio
async def test_load_pods_with_recording_rule(configure):
    configure(
        prometheus_metrics_dialect=MetricDialectName.OTEL,
        prometheus_owner_resolution=OwnerResolutionName.RECORDING_RULE,
    )
    service = FakePrometheusMetricsService(
        responses=[
            [{"metric": {"pod": "mock-pod-1"}}, {"metric": {"pod": "mock-pod-2"}}],
            [{"metric": {"pod": "mock-pod-1"}}, {"metric": {"pod": "mock-pod-2"}}],
        ]
    )

    pods = await service.load_pods(make_object(), timedelta(days=1))

    assert sorted((pod.name, pod.deleted) for pod in pods) == [("mock-pod-1", False), ("mock-pod-2", False)]
    queries = [normalized(query) for query in service.data_queries]
    assert queries[0] == (
        f'last_over_time( {RECORDING_RULE}{{ workload="mock-object-1", workload_type="deployment", '
        'namespace="default" }[24h] )'
    )
    assert queries[1] == 'k8s_pod_phase{ pod=~"mock-pod-1|mock-pod-2", namespace="default" } == 2'


@pytest.mark.asyncio
async def test_load_pods_falls_back_for_kinds_missing_from_recording_rule(configure):
    configure(
        prometheus_metrics_dialect=MetricDialectName.KUBE_STATE_METRICS,
        prometheus_owner_resolution=OwnerResolutionName.RECORDING_RULE,
    )
    service = FakePrometheusMetricsService(responses=[[], []])

    assert await service.load_pods(make_object(kind="Rollout"), timedelta(days=1)) == []
    assert normalized(service.data_queries[0]).startswith("kube_replicaset_owner{")


@pytest.mark.asyncio
async def test_load_pods_uses_hours_for_sub_day_periods(configure):
    configure(prometheus_owner_resolution=OwnerResolutionName.KUBE_STATE_METRICS)
    service = FakePrometheusMetricsService(responses=[[], []])

    await service.load_pods(make_object(kind="StatefulSet"), timedelta(hours=6))

    assert "[6h]" in service.data_queries[0]
