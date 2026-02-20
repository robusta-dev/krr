#!/bin/bash
set -e

# Default strategy
STRATEGY="${KRR_STRATEGY:-${1:-simple}}"

# Build the command as an array
CMD=("python" "/app/krr.py" "${STRATEGY}")

# ==================== Kubernetes Settings ====================
[ -n "${KRR_KUBECONFIG}" ] && CMD+=("--kubeconfig=${KRR_KUBECONFIG}")
[ -n "${KRR_AS}" ] && CMD+=("--as=${KRR_AS}")
[ -n "${KRR_AS_GROUP}" ] && CMD+=("--as-group=${KRR_AS_GROUP}")
[ -n "${KRR_CONTEXT}" ] && CMD+=("--context=${KRR_CONTEXT}")
[ "${KRR_ALL_CLUSTERS}" = "true" ] && CMD+=("--all-clusters")
[ -n "${KRR_NAMESPACE}" ] && CMD+=("--namespace=${KRR_NAMESPACE}")
[ -n "${KRR_RESOURCE}" ] && CMD+=("--resource=${KRR_RESOURCE}")
[ -n "${KRR_SELECTOR}" ] && CMD+=("--selector=${KRR_SELECTOR}")

# ==================== Prometheus Settings ====================
[ -n "${KRR_PROMETHEUS_URL}" ] && CMD+=("--prometheus-url=${KRR_PROMETHEUS_URL}")
[ -n "${KRR_PROMETHEUS_AUTH_HEADER}" ] && CMD+=("--prometheus-auth-header=${KRR_PROMETHEUS_AUTH_HEADER}")
[ -n "${KRR_PROMETHEUS_HEADERS}" ] && CMD+=("--prometheus-headers=${KRR_PROMETHEUS_HEADERS}")
[ "${KRR_PROMETHEUS_SSL_ENABLED}" = "true" ] && CMD+=("--prometheus-ssl-enabled")
[ -n "${KRR_PROMETHEUS_CLUSTER_LABEL}" ] && CMD+=("--prometheus-cluster-label=${KRR_PROMETHEUS_CLUSTER_LABEL}")
[ -n "${KRR_PROMETHEUS_LABEL}" ] && CMD+=("--prometheus-label=${KRR_PROMETHEUS_LABEL}")

# ==================== Prometheus EKS Settings ====================
[ "${KRR_EKS_MANAGED_PROM}" = "true" ] && CMD+=("--eks-managed-prom")
[ -n "${KRR_EKS_PROFILE_NAME}" ] && CMD+=("--eks-profile-name=${KRR_EKS_PROFILE_NAME}")
[ -n "${KRR_EKS_ACCESS_KEY}" ] && CMD+=("--eks-access-key=${KRR_EKS_ACCESS_KEY}")
[ -n "${KRR_EKS_SECRET_KEY}" ] && CMD+=("--eks-secret-key=${KRR_EKS_SECRET_KEY}")
[ -n "${KRR_EKS_SERVICE_NAME}" ] && CMD+=("--eks-service-name=${KRR_EKS_SERVICE_NAME}")
[ -n "${KRR_EKS_MANAGED_PROM_REGION}" ] && CMD+=("--eks-managed-prom-region=${KRR_EKS_MANAGED_PROM_REGION}")
[ -n "${KRR_EKS_ASSUME_ROLE}" ] && CMD+=("--eks-assume-role=${KRR_EKS_ASSUME_ROLE}")

# ==================== Prometheus Coralogix Settings ====================
[ -n "${KRR_CORALOGIX_TOKEN}" ] && CMD+=("--coralogix-token=${KRR_CORALOGIX_TOKEN}")

# ==================== Prometheus Openshift Settings ====================
[ "${KRR_OPENSHIFT}" = "true" ] && CMD+=("--openshift")

# ==================== Prometheus GCP Settings ====================
[ "${KRR_GCP_ANTHOS}" = "true" ] && CMD+=("--gcp-anthos")

# ==================== Recommendation Settings ====================
[ -n "${KRR_CPU_MIN}" ] && CMD+=("--cpu-min=${KRR_CPU_MIN}")
[ -n "${KRR_MEM_MIN}" ] && CMD+=("--mem-min=${KRR_MEM_MIN}")

# ==================== Threading Settings ====================
[ -n "${KRR_MAX_WORKERS}" ] && CMD+=("--max-workers=${KRR_MAX_WORKERS}")

# ==================== Job Grouping Settings ====================
[ -n "${KRR_JOB_GROUPING_LABELS}" ] && CMD+=("--job-grouping-labels=${KRR_JOB_GROUPING_LABELS}")
[ -n "${KRR_JOB_GROUPING_LIMIT}" ] && CMD+=("--job-grouping-limit=${KRR_JOB_GROUPING_LIMIT}")

# ==================== Job Discovery Settings ====================
[ -n "${KRR_DISCOVERY_JOB_BATCH_SIZE}" ] && CMD+=("--discovery-job-batch-size=${KRR_DISCOVERY_JOB_BATCH_SIZE}")
[ -n "${KRR_DISCOVERY_JOB_MAX_BATCHES}" ] && CMD+=("--discovery-job-max-batches=${KRR_DISCOVERY_JOB_MAX_BATCHES}")

# ==================== Logging Settings ====================
[ -n "${KRR_FORMATTER}" ] && CMD+=("--formatter=${KRR_FORMATTER}")
[ "${KRR_VERBOSE}" = "true" ] && CMD+=("--verbose")
[ "${KRR_QUIET}" = "true" ] && CMD+=("--quiet")
[ "${KRR_LOGTOSTDERR}" = "true" ] && CMD+=("--logtostderr")
[ -n "${KRR_WIDTH}" ] && CMD+=("--width=${KRR_WIDTH}")

# ==================== Output Settings ====================
[ "${KRR_SHOW_CLUSTER_NAME}" = "true" ] && CMD+=("--show-cluster-name")
[ "${KRR_EXCLUDE_SEVERITY}" = "false" ] && CMD+=("--exclude-severity")
[ -n "${KRR_FILEOUTPUT}" ] && CMD+=("--fileoutput=${KRR_FILEOUTPUT}")
[ "${KRR_FILEOUTPUT_DYNAMIC}" = "true" ] && CMD+=("--fileoutput-dynamic")
[ -n "${KRR_SLACKOUTPUT}" ] && CMD+=("--slackoutput=${KRR_SLACKOUTPUT}")
[ -n "${KRR_SLACKTITLE}" ] && CMD+=("--slacktitle=${KRR_SLACKTITLE}")
[ -n "${KRR_AZUREBLOBOUTPUT}" ] && CMD+=("--azurebloboutput=${KRR_AZUREBLOBOUTPUT}")
[ -n "${KRR_TEAMS_WEBHOOK}" ] && CMD+=("--teams-webhook=${KRR_TEAMS_WEBHOOK}")
[ -n "${KRR_AZURE_SUBSCRIPTION_ID}" ] && CMD+=("--azure-subscription-id=${KRR_AZURE_SUBSCRIPTION_ID}")
[ -n "${KRR_AZURE_RESOURCE_GROUP}" ] && CMD+=("--azure-resource-group=${KRR_AZURE_RESOURCE_GROUP}")

# ==================== Publish Scan Settings ====================
[ -n "${KRR_PUBLISH_SCAN_URL}" ] && CMD+=("--publish_scan_url=${KRR_PUBLISH_SCAN_URL}")
[ -n "${KRR_START_TIME}" ] && CMD+=("--start_time=${KRR_START_TIME}")
[ -n "${KRR_SCAN_ID}" ] && CMD+=("--scan_id=${KRR_SCAN_ID}")
[ -n "${KRR_NAMED_SINKS}" ] && CMD+=("--named_sinks=${KRR_NAMED_SINKS}")

# ==================== Strategy Settings (Common) ====================
[ -n "${KRR_HISTORY_DURATION}" ] && CMD+=("--history-duration=${KRR_HISTORY_DURATION}")
[ -n "${KRR_TIMEFRAME_DURATION}" ] && CMD+=("--timeframe-duration=${KRR_TIMEFRAME_DURATION}")
[ -n "${KRR_POINTS_REQUIRED}" ] && CMD+=("--points-required=${KRR_POINTS_REQUIRED}")
[ "${KRR_ALLOW_HPA}" = "true" ] && CMD+=("--allow-hpa")
[ "${KRR_USE_OOMKILL_DATA}" = "true" ] && CMD+=("--use-oomkill-data")

# ==================== Strategy: simple ====================
if [ "$STRATEGY" = "simple" ]; then
    [ -n "${KRR_CPU_PERCENTILE}" ] && CMD+=("--cpu-percentile=${KRR_CPU_PERCENTILE}")
    [ -n "${KRR_MEMORY_BUFFER_PERCENTAGE}" ] && CMD+=("--memory-buffer-percentage=${KRR_MEMORY_BUFFER_PERCENTAGE}")
    [ -n "${KRR_OOM_MEMORY_BUFFER_PERCENTAGE}" ] && CMD+=("--oom-memory-buffer-percentage=${KRR_OOM_MEMORY_BUFFER_PERCENTAGE}")
fi

# ==================== Strategy: simple-limit ====================
if [ "$STRATEGY" = "simple-limit" ]; then
    [ -n "${KRR_CPU_REQUEST}" ] && CMD+=("--cpu-request=${KRR_CPU_REQUEST}")
    [ -n "${KRR_CPU_LIMIT}" ] && CMD+=("--cpu-limit=${KRR_CPU_LIMIT}")
    [ -n "${KRR_MEMORY_BUFFER_PERCENTAGE}" ] && CMD+=("--memory-buffer-percentage=${KRR_MEMORY_BUFFER_PERCENTAGE}")
    [ -n "${KRR_OOM_MEMORY_BUFFER_PERCENTAGE}" ] && CMD+=("--oom-memory-buffer-percentage=${KRR_OOM_MEMORY_BUFFER_PERCENTAGE}")
fi

# ==================== Strategy: ai-assisted ====================
if [ "$STRATEGY" = "ai-assisted" ]; then
    [ -n "${KRR_AI_PROVIDER}" ] && CMD+=("--ai-provider=${KRR_AI_PROVIDER}")
    [ -n "${KRR_AI_MODEL}" ] && CMD+=("--ai-model=${KRR_AI_MODEL}")
    [ -n "${KRR_AI_API_KEY}" ] && CMD+=("--ai-api-key=${KRR_AI_API_KEY}")
    [ -n "${KRR_AI_TEMPERATURE}" ] && CMD+=("--ai-temperature=${KRR_AI_TEMPERATURE}")
    [ -n "${KRR_AI_MAX_TOKENS}" ] && CMD+=("--ai-max-tokens=${KRR_AI_MAX_TOKENS}")
    [ "${KRR_AI_COMPACT_MODE}" = "true" ] && CMD+=("--ai-compact-mode")
    [ "${KRR_AI_EXCLUDE_SIMPLE_REFERENCE}" = "true" ] && CMD+=("--ai-exclude-simple-reference")
    [ -n "${KRR_AI_TIMEOUT}" ] && CMD+=("--ai-timeout=${KRR_AI_TIMEOUT}")
    [ -n "${KRR_CPU_PERCENTILE}" ] && CMD+=("--cpu-percentile=${KRR_CPU_PERCENTILE}")
    [ -n "${KRR_MEMORY_BUFFER_PERCENTAGE}" ] && CMD+=("--memory-buffer-percentage=${KRR_MEMORY_BUFFER_PERCENTAGE}")
fi

echo "Executing: ${CMD[*]}"
exec "${CMD[@]}"
