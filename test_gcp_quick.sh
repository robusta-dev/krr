#!/bin/bash
set -e

if [ ! -f .env ]; then
    echo "Missing .env file with PROJECT_ID/CLUSTER_NAME defaults."
    exit 1
fi

# shellcheck source=/dev/null
set -a
source .env
set +a

# Parametri ottimizzati per evitare rate limiting GCP (429 errors)
HISTORY_DURATION="48"      # Ridotto da 230 a 48 ore (2 giorni)
TIMEFRAME_DURATION="5.0"   # Aumentato da 2.0 a 5.0 minuti

# Aumenta batch size per ridurre numero di query
export KRR_OWNER_BATCH_SIZE=200

LOCATION="global" # GCP Managed Prometheus location
NAMESPACE="${1:-${NAMESPACE:-default}}"  # 1st arg overrides .env/default
if [ -n "${2:-}" ]; then
    CONTEXT="${2}"
fi
if [ -n "${3:-}" ]; then
    USE_ANTHOS="${3}"
fi
# CPU_PERCENTILE="${CPU_PERCENTILE:-95}"
# if [ -n "${4:-}" ]; then
#     CPU_PERCENTILE="${4}"
# fi

if [ -z "${PROJECT_ID:-}" ] || [ -z "${CLUSTER_NAME:-}" ]; then
    echo -e "${RED}Error: PROJECT_ID and CLUSTER_NAME must be defined in .env or via environment variables.${NC}"
    exit 1
fi


# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}KRR GCP Quick Test (Namespace: ${NAMESPACE})${NC}"
echo "=================================================="
echo ""

# Verify Python
PYTHON_CMD=$(command -v python3 || command -v python)

# Get token
echo -e "${YELLOW}Getting GCP token...${NC}"
TOKEN=$(gcloud auth print-access-token 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo -e "${RED}Error: Token not available${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Token obtained${NC}"
echo ""

# Prometheus URL
PROMETHEUS_URL="https://monitoring.googleapis.com/v1/projects/${PROJECT_ID}/location/${LOCATION}/prometheus"

echo "Analyzing namespace: ${NAMESPACE}"
echo "Cluster: ${CLUSTER_NAME}"
if [ -n "$CONTEXT" ]; then
    echo "Context: ${CONTEXT}"
fi
if [ "$USE_ANTHOS" = "anthos" ]; then
    echo "Mode: Anthos (on-prem)"
else
    echo "Mode: GKE Cloud"
fi
echo "CPU Percentile: ${CPU_PERCENTILE}"
echo ""

# Build context flag if provided
CONTEXT_FLAG=""
if [ -n "$CONTEXT" ]; then
    CONTEXT_FLAG="--context=${CONTEXT}"
    if command -v kubectl >/dev/null 2>&1; then
        if ! kubectl --context="$CONTEXT" get namespace "$NAMESPACE" >/dev/null 2>&1; then
            echo -e "${YELLOW}Warning: Unable to verify namespace ${NAMESPACE} via kubectl for context ${CONTEXT}.${NC}"
            echo -e "${YELLOW}         Ensure 'gcloud container fleet memberships get-credentials' was executed and that the context has list permissions.${NC}"
        fi
    else
        echo -e "${YELLOW}kubectl not found in PATH; skipping namespace reachability check.${NC}"
    fi
fi

# Build Anthos flag if requested
ANTHOS_FLAG=""
if [ "$USE_ANTHOS" = "anthos" ]; then
    ANTHOS_FLAG="--gcp-anthos"
fi

#HPA Mode flag
if [ "${HPA_MODE:-false}" = "true" ]; then
    HPA_FLAG="--allow-hpa"
else
    HPA_FLAG=""
fi

# If AI_MODE is true, enable ai-assisted strategy and --ai-model=gemini-3-flash-preview
if [ "${AI_MODE:-false}" = "true" ]; then
    echo -e "${YELLOW}AI Mode enabled: Using AI-assisted strategy with Gemini 3 Flash Preview model.${NC}"

    $PYTHON_CMD krr.py ai-assisted \
        --max-workers=1 \
        $CONTEXT_FLAG \
        --prometheus-url="${PROMETHEUS_URL}" \
        --prometheus-auth-header="Bearer ${TOKEN}" \
        --prometheus-cluster-label="${CLUSTER_NAME}" \
        --prometheus-label="cluster_name" \
        --namespace="${NAMESPACE}" \
        --history-duration="${HISTORY_DURATION}" \
        --timeframe-duration="${TIMEFRAME_DURATION}" \
        --cpu-percentile="${CPU_PERCENTILE}" \
        --memory-buffer-percentage=15 \
        $ANTHOS_FLAG --ai-max-tokens=5000 $HPA_FLAG \
        --formatter table \
        --fileoutput-dynamic --use-oomkill-data --ai-model=gemini-3-flash-preview # --show-cluster-name

else
    echo -e "${YELLOW}AI Mode disabled: Using standard KRR strategies.${NC}"
    $PYTHON_CMD krr.py simple \
        --max-workers=1 \
        $CONTEXT_FLAG \
        --prometheus-url="${PROMETHEUS_URL}" \
        --prometheus-auth-header="Bearer ${TOKEN}" \
        --prometheus-cluster-label="${CLUSTER_NAME}" \
        --prometheus-label="cluster_name" \
        --namespace="${NAMESPACE}" \
        --history-duration="${HISTORY_DURATION}" \
        --timeframe-duration="${TIMEFRAME_DURATION}" \
        --cpu-percentile="${CPU_PERCENTILE}" \
        --memory-buffer-percentage=15 \
        $ANTHOS_FLAG $HPA_FLAG \
        --formatter table \
        --fileoutput-dynamic --use-oomkill-data # --ai-model=gemini-3-flash-preview --show-cluster-name 

fi

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Test completed${NC}"
else
    echo -e "${RED}✗ Test failed (exit code: ${EXIT_CODE})${NC}"
fi

exit $EXIT_CODE
