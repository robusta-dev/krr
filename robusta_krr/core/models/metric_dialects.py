"""
Metric naming dialects for Kubernetes *state* metrics.

KRR needs two kinds of metrics:

1. Container **usage** metrics (``container_cpu_usage_seconds_total``,
   ``container_memory_working_set_bytes``). These come from cAdvisor and are
   assumed to be present under their cAdvisor names in every supported setup.
   An OpenTelemetry Collector can provide them by scraping cAdvisor through the
   ``prometheus`` receiver.

2. Kubernetes **state** metrics (pod phase, pod owners, resource requests and
   limits, node capacity, OOMKill reasons). These are named differently
   depending on who produced them:

   * ``kube-state-metrics`` + ``cAdvisor``/``node-exporter`` (the default), or
   * the OpenTelemetry Collector ``k8s_cluster`` and ``hostmetrics`` receivers.

Only group 2 is described by a :class:`MetricDialect`, so switching dialects
never changes how usage metrics are queried.

Every dialect must expose its series under the Prometheus-conventional
``namespace`` / ``pod`` / ``container`` labels, because that is what the cAdvisor
usage metrics use and the two are joined on those labels. A Collector exporting
resource attributes verbatim produces ``k8s_namespace_name`` / ``k8s_pod_name`` /
``k8s_container_name`` instead, which does not work; map them first, see the
OpenTelemetry section of the README for the transform to do it. Dialect
auto-detection checks for the mapped labels, not only for the metric name, so a
Collector without that mapping is reported instead of being silently accepted.
"""

from __future__ import annotations

import enum

import pydantic as pd


class MetricDialectName(str, enum.Enum):
    AUTO = "auto"
    KUBE_STATE_METRICS = "kube-state-metrics"
    OTEL = "otel"


class OwnerResolutionName(str, enum.Enum):
    AUTO = "auto"
    KUBE_STATE_METRICS = "kube-state-metrics"
    RECORDING_RULE = "recording-rule"


class MetricDialect(pd.BaseModel):
    """
    Metric and label names of a Kubernetes state metrics source.

    Every field is a metric name, a label name, or a PromQL label-selector
    fragment that is interpolated into a query. Selector fragments are used as a
    *prefix* inside the label braces, so they must end with ", " when they are
    not empty. The node selectors are the exception, see below.
    """

    name: MetricDialectName

    # Node capacity, used for the cluster summary. The node selectors carry no
    # trailing comma, they are joined with the cluster label by the caller.
    node_memory_total: str
    node_cpu_total: str
    node_memory_selector: str
    node_cpu_selector: str
    node_group_by_label: str

    # Container resource requests and limits.
    container_memory_request: str
    container_cpu_request: str
    container_memory_limit: str
    # kube-state-metrics encodes the resource in a label, OTel in the metric name.
    memory_resource_selector: str
    cpu_resource_selector: str

    # Pod phase.
    pod_phase_metric: str
    pod_phase_running_selector: str
    # kube-state-metrics exposes one gauge per phase (1 = in this phase), OTel a
    # single gauge holding the phase enum (2 = Running).
    pod_phase_running_value: str

    # OOMKill detection.
    oom_reason_metric: str
    oom_reason_label: str

    # Metric used to detect this dialect when `--prometheus-metrics-dialect auto`,
    # plus the label matcher that tells this dialect apart from a source that
    # exposes the same metric under unmapped labels. No trailing comma.
    probe_metric: str
    probe_selector: str

    class Config:
        allow_mutation = False


KSM_DIALECT = MetricDialect(
    name=MetricDialectName.KUBE_STATE_METRICS,
    # NOTE: machine_memory_bytes / machine_cpu_cores are deprecated and missing
    # in some hosted Prometheus offerings (Azure Managed Prometheus), so the
    # kube-state-metrics capacity metric is used instead.
    node_memory_total="kube_node_status_capacity",
    node_cpu_total="kube_node_status_capacity",
    node_memory_selector='resource="memory"',
    node_cpu_selector='resource="cpu"',
    node_group_by_label="node",
    container_memory_request="kube_pod_container_resource_requests",
    container_cpu_request="kube_pod_container_resource_requests",
    container_memory_limit="kube_pod_container_resource_limits",
    memory_resource_selector='resource="memory", ',
    cpu_resource_selector='resource="cpu", ',
    pod_phase_metric="kube_pod_status_phase",
    pod_phase_running_selector='phase="Running", ',
    pod_phase_running_value="1",
    oom_reason_metric="kube_pod_container_status_last_terminated_reason",
    oom_reason_label="reason",
    probe_metric="kube_pod_status_phase",
    probe_selector="",
)

# Names produced by the OpenTelemetry Collector:
#   node capacity        -> hostmetrics receiver (cpu + memory scrapers)
#   container resources  -> k8s_cluster receiver
#   pod phase            -> k8s_cluster receiver (k8s.pod.phase)
#   OOMKill reason       -> k8s_cluster receiver (k8s.container.status.reason,
#                           disabled by default, must be enabled explicitly)
# k8s.container.status.reason and system.memory.limit are both opt-in, and the
# k8s.* resource attributes have to be mapped onto the namespace / pod /
# container labels. See the README for the Collector configuration.
OTEL_DIALECT = MetricDialect(
    name=MetricDialectName.OTEL,
    node_memory_total="system_memory_limit_bytes",
    node_cpu_total="system_cpu_logical_count",
    node_memory_selector="",
    node_cpu_selector="",
    node_group_by_label="host_name",
    container_memory_request="k8s_container_memory_request_bytes",
    container_cpu_request="k8s_container_cpu_request",
    container_memory_limit="k8s_container_memory_limit_bytes",
    memory_resource_selector="",
    cpu_resource_selector="",
    pod_phase_metric="k8s_pod_phase",
    pod_phase_running_selector="",
    pod_phase_running_value="2",
    oom_reason_metric="k8s_container_status_reason",
    oom_reason_label="k8s_container_status_reason",
    probe_metric="k8s_pod_phase",
    # `namespace` only exists once the Collector maps k8s.namespace.name onto it.
    probe_selector='namespace!=""',
)

# Order matters: auto-detection probes dialects in this order and keeps the
# first one that returns data, so an existing kube-state-metrics setup always
# resolves to the same queries it used before dialects existed.
DIALECTS: tuple[MetricDialect, ...] = (KSM_DIALECT, OTEL_DIALECT)

DEFAULT_DIALECT = KSM_DIALECT

_BY_NAME = {dialect.name: dialect for dialect in DIALECTS}


def get_dialect(name: MetricDialectName) -> MetricDialect:
    """
    Returns the dialect for an explicit dialect name.

    Raises:
        ValueError: if called with MetricDialectName.AUTO, which has to be
            resolved by probing Prometheus instead.
    """

    if name == MetricDialectName.AUTO:
        raise ValueError("MetricDialectName.AUTO must be resolved by probing, not by name")
    return _BY_NAME[name]
