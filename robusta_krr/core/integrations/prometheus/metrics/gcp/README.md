# GCP Managed Prometheus Metric Loaders

This package contains metric loaders specific to Google Cloud Platform Managed Prometheus.

## Overview

GCP Managed Prometheus uses different metric naming conventions from standard Prometheus:

| Standard Metric | GCP Metric |
|----------------|------------|
| `container_cpu_usage_seconds_total` | `kubernetes.io/container/cpu/core_usage_time` |
| `container_memory_working_set_bytes` | `kubernetes.io/container/memory/used_bytes` |

Additionally, GCP requires UTF-8 PromQL syntax with quoted metric names and labels:
```promql
{"__name__"="kubernetes.io/container/cpu/core_usage_time","namespace_name"="default"}
```

## Implemented Loaders

### CPU Loaders

#### `GcpCPULoader`
Loads CPU usage data using `rate()` on the `kubernetes.io/container/cpu/core_usage_time` metric.

**Query Type**: `QueryRange`

**Example generated query**:
```promql
label_replace(
    label_replace(
        max(
            rate(
                {"__name__"="kubernetes.io/container/cpu/core_usage_time",
                 "monitored_resource"="k8s_container",
                 "namespace_name"="default",
                 "pod_name"=~"my-pod-.*",
                 "container_name"="app"}[30s]
            )
        ) by (container_name, pod_name, job),
        "pod", "$1", "pod_name", "(.+)"
    ),
    "container", "$1", "container_name", "(.+)"
)
```

#### `GcpPercentileCPULoader(percentile: float)`
Factory that creates a loader for the specified percentile of CPU usage.

**Parameters**:
- `percentile`: Value between 0 and 100 (e.g., 95 for the 95th percentile)

**Function**: Uses `quantile_over_time()` to calculate the specified percentile

#### `GcpCPUAmountLoader`
Counts the number of available CPU data points using `count_over_time()`.

### Memory Loaders

#### `GcpMemoryLoader`
Loads memory usage data from the `kubernetes.io/container/memory/used_bytes` metric.

**Query Type**: `QueryRange`

#### `GcpMaxMemoryLoader`
Loads the maximum memory usage over the specified period using `max_over_time()`.

#### `GcpMemoryAmountLoader`
Counts the number of available memory data points using `count_over_time()`.

## Label Renaming

All GCP loaders use `label_replace()` to rename GCP labels to standard Prometheus labels:

- `pod_name` → `pod`
- `container_name` → `container`

This ensures compatibility with the rest of the KRR code that expects standard labels.

## Special GCP Labels

All loaders automatically include the label:
```promql
"monitored_resource"="k8s_container"
```

This label is required by GCP Managed Prometheus to identify Kubernetes container metrics.

## Usage

GCP loaders are used automatically when:
1. The Prometheus URL contains `monitoring.googleapis.com`
2. The `GcpManagedPrometheusMetricsService` is active

No need to modify existing strategies (`SimpleStrategy`, `SimpleLimitStrategy`) as the mapping is handled automatically by the GCP service.

## Limitations

- **MaxOOMKilledMemoryLoader**: Not implemented because it depends on `kube-state-metrics` which may not be available in GCP Managed Prometheus.

## Integration Example

```python
from robusta_krr.core.integrations.prometheus.metrics.gcp import (
    GcpCPULoader,
    GcpPercentileCPULoader,
    GcpMemoryLoader,
)

# Automatic usage via the service
# The service automatically maps:
# PercentileCPULoader(95) → GcpPercentileCPULoader(95)
# MaxMemoryLoader → GcpMaxMemoryLoader
# etc.
```

## Files

- `__init__.py`: Exports all loaders
- `cpu.py`: CPU metric loaders
- `memory.py`: Memory metric loaders
- `anthos/`: Anthos-specific metric loaders

## See Also

- [GCP Managed Prometheus Integration Guide](../../../../../../docs/gcp-managed-prometheus-integration.md)
- [Base Metric Loader](../base.py)
- [GCP Metrics Service](../../metrics_service/gcp_metrics_service.py)
- [Anthos Metrics Service](../../metrics_service/anthos_metrics_service.py)
