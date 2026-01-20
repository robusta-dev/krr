# GCP Managed Prometheus Integration for KRR

## Overview

This integration enables KRR (Kubernetes Resource Recommender) to work with Google Cloud Platform Managed Prometheus, which uses different metric naming conventions from standard Prometheus.

## Differences Between Standard Prometheus and GCP

### Metric Names
- **Standard Prometheus**: `container_cpu_usage_seconds_total`, `container_memory_working_set_bytes`
- **GCP Managed Prometheus**: `kubernetes.io/container/cpu/core_usage_time`, `kubernetes.io/container/memory/used_bytes`

### PromQL Syntax
- **Standard**: `container_cpu_usage_seconds_total{namespace="default"}`
- **GCP (UTF-8)**: `{"__name__"="kubernetes.io/container/cpu/core_usage_time","namespace_name"="default"}`

### Label Names
- **Standard**: `namespace`, `pod`, `container`
- **GCP**: `namespace_name`, `pod_name`, `container_name`, `monitored_resource="k8s_container"`

## Usage

### 1. Authentication

Before running KRR with GCP Managed Prometheus, ensure you have a valid authentication token:

```bash
export TOKEN=$(gcloud auth print-access-token)
```

### 2. GCP Managed Prometheus URL

The URL follows this pattern:
```
https://monitoring.googleapis.com/v1/projects/{PROJECT_ID}/location/global/prometheus
```

For example:
```
https://monitoring.googleapis.com/v1/projects/sicraweb-evo-dev/location/global/prometheus
```

### 3. Running KRR

KRR automatically detects GCP Managed Prometheus from the URL and uses the appropriate GCP loaders:

```bash
python krr.py simple \
  --prometheus-url="https://monitoring.googleapis.com/v1/projects/sicraweb-evo-dev/location/global/prometheus" \
  --prometheus-auth-header="Bearer $TOKEN" \
  --cluster=autopilot-cluster-sicra-dev
```

Or using the cluster label if you have multiple clusters in the same project:

```bash
python krr.py simple \
  --prometheus-url="https://monitoring.googleapis.com/v1/projects/sicraweb-evo-dev/location/global/prometheus" \
  --prometheus-auth-header="Bearer $TOKEN" \
  --prometheus-cluster-label="autopilot-cluster-sicra-dev" \
  --prometheus-label="cluster_name"
```

### 4. Script Example

You can also use a script like `local.sh` to automate the process:

```bash
#!/bin/bash

export PROJECT_ID="your-gcp-project-id"
export CLUSTER_NAME="your-cluster-name"
export TOKEN=$(gcloud auth print-access-token)

python krr.py simple \
  --prometheus-url="https://monitoring.googleapis.com/v1/projects/${PROJECT_ID}/location/global/prometheus" \
  --prometheus-auth-header="Bearer ${TOKEN}" \
  --prometheus-cluster-label="${CLUSTER_NAME}" \
  --prometheus-label="cluster_name" \
  --history-duration=12 \
  --cpu-percentile=95 \
  --memory-buffer-percentage=15
```

### 5. Anthos Support

For GCP Anthos (on-premises Kubernetes managed by Google), use the `--gcp-anthos` flag:

```bash
python krr.py simple \
  --prometheus-url="https://monitoring.googleapis.com/v1/projects/${PROJECT_ID}/location/global/prometheus" \
  --prometheus-auth-header="Bearer ${TOKEN}" \
  --gcp-anthos \
  --namespace=your-namespace
```

See [CHANGES_GCP.md](../CHANGES_GCP.md) for detailed GCP and Anthos documentation.

## Integration Architecture

### Created Components

1. **GCP Metric Loaders** (`robusta_krr/core/integrations/prometheus/metrics/gcp/`)
   - `GcpCPULoader`: Loads CPU metrics from GCP
   - `GcpPercentileCPULoader`: Factory for CPU percentiles (saves percentile as `_percentile` attribute)
   - `GcpCPUAmountLoader`: Counts CPU data points
   - `GcpMemoryLoader`: Loads memory metrics from GCP
   - `GcpMaxMemoryLoader`: Maximum memory usage
   - `GcpMemoryAmountLoader`: Counts memory data points
   - `GcpMaxOOMKilledMemoryLoader`: Inference-based OOM detection using restart_count + memory limits

2. **Anthos Metric Loaders** (`robusta_krr/core/integrations/prometheus/metrics/gcp/anthos/`)
   - `AnthosCPULoader`: Loads CPU metrics from Anthos
   - `AnthosPercentileCPULoader`: Factory for Anthos CPU percentiles
   - `AnthosCPUAmountLoader`: Counts Anthos CPU data points
   - `AnthosMemoryLoader`: Loads memory metrics from Anthos
   - `AnthosMaxMemoryLoader`: Maximum Anthos memory usage
   - `AnthosMemoryAmountLoader`: Counts Anthos memory data points
   - `AnthosMaxOOMKilledMemoryLoader`: Inference-based OOM detection using restart_count + memory limits

3. **GCP Metrics Service** (`robusta_krr/core/integrations/prometheus/metrics_service/gcp_metrics_service.py`)
   - Extends `PrometheusMetricsService`
   - Automatically maps standard loaders to GCP loaders
   - Handles `PercentileCPULoader` factory pattern using `_percentile` attribute
   - Implements inference-based OOM detection via `GcpMaxOOMKilledMemoryLoader`

4. **Anthos Metrics Service** (`robusta_krr/core/integrations/prometheus/metrics_service/anthos_metrics_service.py`)
   - Extends `PrometheusMetricsService`
   - Maps standard loaders to Anthos loaders
   - Returns empty list from `load_pods()` (no kube-state-metrics in Anthos)
   - Uses Kubernetes API for pod discovery

5. **Auto-detection** (`robusta_krr/core/integrations/prometheus/loader.py`)
   - Automatically detects `monitoring.googleapis.com` in URL
   - Selects `GcpManagedPrometheusMetricsService` or `AnthosMetricsService` as appropriate

6. **Test Suites**
   - `tests/test_gcp_loaders.py`: Unit tests for all GCP loaders
   - `tests/test_anthos_loaders.py`: Unit tests for all Anthos loaders
   - Verifies correct UTF-8 syntax
   - Validates cluster label handling
   - Verifies factory pattern for PercentileCPULoader

### Loader Mapping

The GCP service automatically maps:
- `CPULoader` → `GcpCPULoader`
- `PercentileCPULoader(percentile)` → `GcpPercentileCPULoader(percentile)`
- `CPUAmountLoader` → `GcpCPUAmountLoader`
- `MemoryLoader` → `GcpMemoryLoader`
- `MaxMemoryLoader` → `GcpMaxMemoryLoader`
- `MemoryLoader` → `GcpMemoryLoader`
- `MaxMemoryLoader` → `GcpMaxMemoryLoader`
- `MemoryAmountLoader` → `GcpMemoryAmountLoader`
- `MaxOOMKilledMemoryLoader` → `GcpMaxOOMKilledMemoryLoader` (inference-based)

The Anthos service automatically maps to Anthos-specific loaders using `kubernetes.io/anthos/container/*` metrics, including `AnthosMaxOOMKilledMemoryLoader` for OOM detection.

### Label Renaming

GCP loaders use `label_replace()` to rename GCP labels to standard labels:
- `pod_name` → `pod`
- `container_name` → `container`

This ensures compatibility with existing KRR code that expects standard Prometheus labels.

## Limitations

1. **MaxOOMKilledMemoryLoader (OOM Detection)**: GCP/Anthos Managed Prometheus does not provide `kube_pod_container_status_last_terminated_reason` metric that explicitly reports OOMKilled events. Instead, KRR uses an **inference-based approach** that combines two metrics:

   - `kubernetes.io/container/memory/limit_bytes` (or `kubernetes.io/anthos/container/memory/limit_bytes` for Anthos)
   - `kubernetes.io/container/restart_count` (or `kubernetes.io/anthos/container/restart_count` for Anthos)

   **Query Structure (GCP):**
   ```promql
   max_over_time(
       max(
           max(
               {"__name__"="kubernetes.io/container/memory/limit_bytes",
                   "monitored_resource"="k8s_container",
                   "namespace_name"="<namespace>",
                   "pod_name"=~"<pods>",
                   "container_name"="<container>"}
           ) by (pod_name, container_name, job)
           
           * on(pod_name, container_name, job) group_left()
           
           max(
               {"__name__"="kubernetes.io/container/restart_count",
                   "monitored_resource"="k8s_container",
                   "namespace_name"="<namespace>",
                   "pod_name"=~"<pods>",
                   "container_name"="<container>"}
           ) by (pod_name, container_name, job)
       ) by (container_name, pod_name, job)
       [<duration>:<step>]
   )
   ```

   **Important Limitations:**
   - **False Positives**: This approach may report false positives when containers restart for reasons other than OOM (e.g., application crashes, health check failures) while memory usage is high.
   - **Inference-Based**: Unlike standard Prometheus with kube-state-metrics, this does not use explicit Kubernetes OOMKilled events but infers OOM conditions from restart patterns and memory limits.
   - **Best Effort**: Results should be interpreted as potential OOM events rather than confirmed OOMKilled terminations.

   When the flag `--use-oomkill-data` is used, you'll see debug logs indicating "GCP OOM detection query (inference-based)" or "Anthos OOM detection query (inference-based)" to remind you of this limitation.

2. **Token Expiration**: GCP authentication tokens expire. Make sure to regenerate the token if execution takes a long time or if you receive authentication errors.

3. **Cluster Label**: If you have multiple clusters in the same GCP project, you must specify `--prometheus-cluster-label` and `--prometheus-label` to filter data for the correct cluster.

4. **Anthos Pod Discovery**: Anthos does not provide kube-state-metrics, so pod discovery always uses Kubernetes API instead of Prometheus. This is expected behavior and logged at DEBUG level.

## Recent Changes

**2026-01-20**: Implemented OOM detection for GCP and Anthos:
- ✅ Added `GcpMaxOOMKilledMemoryLoader` with inference-based OOM detection
- ✅ Added `AnthosMaxOOMKilledMemoryLoader` with inference-based OOM detection
- ✅ OOM detection uses `memory/limit_bytes` + `restart_count` metrics combination
- ✅ Added debug logging to indicate inference-based approach
- ✅ Updated documentation with query examples and limitations

**2025-11-20**: Implemented the following improvements:
- ✅ Saved `percentile` as class attribute in `GcpPercentileCPULoader` to avoid regex parsing
- ✅ Added explicit handling of `MaxOOMKilledMemoryLoader` (unsupported) in LOADER_MAPPING
- ✅ Improved `cluster_label` handling in UTF-8 syntax
- ✅ Added detailed logging for debugging
- ✅ Created comprehensive test suite for GCP loaders
- ✅ Fixed query syntax to avoid duplicate commas
- ✅ Implemented complete Anthos support with dedicated loaders and service
- ✅ Added `--gcp-anthos` CLI flag for Anthos clusters
- ✅ Created 10 Anthos-specific tests (all passing)
- ✅ Changed pod discovery fallback logging from WARNING to DEBUG level

## Troubleshooting

### Error: "No PercentileCPULoader metrics"

Verify that:
1. The Prometheus URL is correct
2. The authentication token is valid: `gcloud auth print-access-token`
3. The cluster name and project ID are correct
4. Managed Service for Prometheus is enabled in your GCP project

### Error: "Couldn't connect to GCP Managed Prometheus"

Verify:
1. Network connectivity to `monitoring.googleapis.com`
2. IAM permissions to access Cloud Monitoring
3. That the Managed Prometheus service is enabled

### Manual Test Query

You can test the connection with a manual query:

```bash
TOKEN=$(gcloud auth print-access-token)
QUERY='sum(rate({"__name__"="kubernetes.io/container/cpu/core_usage_time","monitored_resource"="k8s_container"}[5m]))'

curl -H "Authorization: Bearer $TOKEN" \
  "https://monitoring.googleapis.com/v1/projects/sicraweb-evo-dev/location/global/prometheus/api/v1/query?query=${QUERY}"
```

### Testing Anthos Metrics

For Anthos, test with anthos-specific metrics:

```bash
TOKEN=$(gcloud auth print-access-token)
QUERY='sum(rate({"__name__"="kubernetes.io/anthos/container/cpu/core_usage_time","monitored_resource"="k8s_container"}[5m]))'

curl -H "Authorization: Bearer $TOKEN" \
  "https://monitoring.googleapis.com/v1/projects/potent-bloom-361714/location/global/prometheus/api/v1/query?query=${QUERY}"
```

## References

- [GCP Managed Prometheus Documentation](https://cloud.google.com/stackdriver/docs/managed-prometheus)
- [UTF-8 PromQL Syntax](https://cloud.google.com/monitoring/api/v3/promql-syntax)
- [KRR Documentation](https://github.com/robusta-dev/krr)
- [GCP & Anthos Implementation Guide](../CHANGES_GCP.md)
