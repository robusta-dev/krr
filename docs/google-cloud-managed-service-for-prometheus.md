## Installation instructions for [Google Managed Service for Prometheus](https://cloud.google.com/stackdriver/docs/managed-prometheus)

The following instructions assume that you are running [Google Managed Service for Prometheus (GMP)](https://cloud.google.com/stackdriver/docs/managed-prometheus) in its [managed collection](https://cloud.google.com/stackdriver/docs/managed-prometheus/setup-managed) mode and that you have installed krr.

krr depends upon 2 [cAdvisor](https://github.com/google/cadvisor) [metrics](https://github.com/google/cadvisor/blob/master/docs/storage/prometheus.md#prometheus-container-metrics):

1. `container_cpu_usage_seconds_total`
1. `container_memory_working_set_bytes`


In order for krr to work with GMP, we need to ensure that cAdvisor is enabled and that the GMP Operator is configured to collect these 2 metrics. This can be combined into a single step that involves revising the GMP Operator configuration file `operatorconfig/config` in Namespace `gmp-public`

Google provides instructions for enabling [Kubelet/cAdvisor](https://cloud.google.com/stackdriver/docs/managed-prometheus/exporters/kubelet-cadvisor). This requires adding a `kubeletScraping` section to the configuration file.

We must also add a `filter` section to the configuration file. The `filter` matches the 2 metrics that krr uses.

`operatorconfig.krr.patch.yaml`:
```YAML
collection:
  filter:
    matchOneOf:
    - '{__name__="container_cpu_usage_seconds_total"}'
    - '{__name__="container_memory_working_set_bytes"}'
  kubeletScraping:
    interval: 30s
```

There are various ways to make this Resource change to the cluster.

You can `kubectl edit` the file and manually add the changes:

```bash
KUBE_EDITOR="nano" \
kubectl edit operatorconfig/config \
--namespace=gmp-public
```

Or you can `kubectl patch` the file:

```bash
kubectl patch operatorconfig/config \
--namespace=gmp-public \
--type=merge \
--patch-file=/path/to/operatorconfig.krr.patch.yaml
```

### Test

There are multiple ways to confirm that GMP is collecting the metrics needed by krr.

The simplest is to access Google Cloud Console "Metric Diagnostics" and confirm that the "Metrics" section includes the 2 metrics with (recent) "Metric Data Ingested":

`https://console.cloud.google.com/monitoring/metrics-diagnostics?project={project}`

> **NOTE** Replace `{project}` with your Google Cloud Project ID.

Another way is to deploy the [Frontend UI for GMP](https://cloud.google.com/stackdriver/docs/managed-prometheus/query#promui-deploy) and use the UI to browse the metrics.

GMP implements the [Prometheus HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/) and, like krr, we can use this to query the metrics:

```bash
PROJECT="..." # Google Cloud Project ID
MONITORING="https://monitoring.googleapis.com/v1"
ENDPOINT="${MONITORING}/projects/${PROJECT}/location/global/prometheus"

TOKEN=$(gcloud auth print-access-token)

# Either
QUERY="count({__name__=\"container_cpu_usage_seconds_total\"})"
# Or
QUERY="count({__name__=\"container_memory_working_set_bytes\"})"

curl \
--silent \
--get \
--header "Authorization: Bearer ${TOKEN}" \
--data-urlencode "query=${QUERY}" \
${ENDPOINT}/api/v1/query
```
If you have [jq]() installed, you can filter the results to output only the latest value:
```bash
| jq -r .data.result[0].value[1]
```

### Run krr

krr leverages Google [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/application-default-credentials). Ensure that ADC credentials are accessible (per Google's documentation) before running krr so that krr can authenticate to GMP.

```bash
PROJECT="..." # Google Cloud Project ID
MONITORING="https://monitoring.googleapis.com/v1"
ENDPOINT="${MONITORING}/projects/${PROJECT}/location/global/prometheus"

python krr.py simple \
--prometheus-url=${ENDPOINT}
```
