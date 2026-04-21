#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Load configuration from .env
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

set -a
source .env
set +a

# All Linux namespaces to process
NAMESPACES=(
    "accounting-service"
    "assegnazione-lavori"
    "bilancio"
    "cartellini"
    "cantieri"
    "preventivi"
    "contabilita-riba"
    "documenti"
    "fornitori"
    "magazzino"
    "office-automation"
    "reportistica"
    "risorse-umane"
)

# Validate required variables
if [ -z "${PROJECT_ID}" ] || [ -z "${CLUSTER_NAME}" ]; then
    echo -e "${RED}Error: PROJECT_ID and CLUSTER_NAME must be set in .env${NC}"
    exit 1
fi

# Get GCP token
echo -e "${YELLOW}→ Getting GCP access token...${NC}"
TOKEN=$(gcloud auth print-access-token 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo -e "${RED}✗ Failed to get GCP token${NC}"
    echo "Run: gcloud auth login"
    exit 1
fi
echo -e "${GREEN}✓ Token obtained${NC}"
echo ""

# Determine which image to use
DOCKER_IMAGE="${KRR_DOCKER_IMAGE:-krr:latest}"

# Build/pull image if needed
echo -e "${YELLOW}→ Checking Docker image...${NC}"
if [[ "${DOCKER_IMAGE}" == *"pkg.dev"* ]]; then
    # Remote image from Artifact Registry
    echo -e "${GREEN}Using remote image: ${DOCKER_IMAGE}${NC}"
    docker pull "${DOCKER_IMAGE}" 2>/dev/null || echo -e "${YELLOW}⚠ Could not pull image, using cached version${NC}"
else
    # Local image
    if ! docker image inspect "${DOCKER_IMAGE}" >/dev/null 2>&1; then
        echo -e "${YELLOW}→ Building Docker image...${NC}"
        docker build -f Dockerfile.gcloud -t "${DOCKER_IMAGE}" .
        echo -e "${GREEN}✓ Image built${NC}"
    fi
fi
echo ""

# Create output directory
mkdir -p ./output

# Determine strategy
if [ "${AI_MODE}" = "true" ]; then
    STRATEGY="ai-assisted"
else
    STRATEGY="simple"
fi

# Convert USE_ANTHOS
if [ "${USE_ANTHOS}" = "anthos" ]; then
    GCP_ANTHOS_VALUE="true"
else
    GCP_ANTHOS_VALUE="false"
fi

# Counters
TOTAL=${#NAMESPACES[@]}
SUCCESSES=0
FAILURES=0

# Log file
LOG_FILE="./output/krr-batch-$(date +%Y%m%d-%H%M%S).log"

echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       KRR Docker - All Namespaces Runner         ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "Project:        ${PROJECT_ID}"
echo "Cluster:        ${CLUSTER_NAME}"
echo "Total NS:       ${TOTAL}"
echo "Strategy:       ${STRATEGY}"
echo "Mode:           $([ "$USE_ANTHOS" = "anthos" ] && echo "Anthos" || echo "GKE")"
echo "AI Enabled:     ${AI_MODE:-false}"
echo "Log:            ${LOG_FILE}"
echo "=================================================="
echo ""

for i in "${!NAMESPACES[@]}"; do
    NS="${NAMESPACES[$i]}"
    COUNTER=$((i + 1))
    
    echo -e "${BLUE}[$COUNTER/$TOTAL]${NC} ${GREEN}Processing: ${NS}${NC}" | tee -a "$LOG_FILE"
    echo "==================================================" | tee -a "$LOG_FILE"
    
    # Capture output to temp file
    TEMP_OUTPUT=$(mktemp)
    
    docker run --rm \
      -v "${HOME}/.kube/config:/root/.kube/config:ro" \
      -e CLOUDSDK_AUTH_ACCESS_TOKEN="${TOKEN}" \
      -e KRR_STRATEGY="${STRATEGY}" \
      -e KRR_PROMETHEUS_URL="https://monitoring.googleapis.com/v1/projects/${PROJECT_ID}/location/global/prometheus" \
      -e KRR_PROMETHEUS_AUTH_HEADER="Bearer ${TOKEN}" \
      -e KRR_PROMETHEUS_CLUSTER_LABEL="${CLUSTER_NAME}" \
      -e KRR_PROMETHEUS_LABEL="cluster_name" \
      ${CONTEXT:+-e KRR_CONTEXT="${CONTEXT}"} \
      -e KRR_NAMESPACE="${NS}" \
      -e KRR_HISTORY_DURATION="${HISTORY_DURATION:-48}" \
      -e KRR_TIMEFRAME_DURATION="${TIMEFRAME_DURATION:-5.0}" \
      -e KRR_CPU_PERCENTILE="${CPU_PERCENTILE:-95}" \
      -e KRR_MEMORY_BUFFER_PERCENTAGE="${MEMORY_BUFFER_PERCENTAGE:-15}" \
      -e KRR_MAX_WORKERS="${MAX_WORKERS:-1}" \
      -e KRR_GCP_ANTHOS="${GCP_ANTHOS_VALUE}" \
      -e KRR_USE_OOMKILL_DATA="${USE_OOMKILL_DATA:-true}" \
      -e KRR_FORMATTER="${FORMATTER:-table}" \
      -e KRR_FILEOUTPUT_DYNAMIC="${FILEOUTPUT_DYNAMIC:-true}" \
      ${HPA_MODE:+-e KRR_ALLOW_HPA="${HPA_MODE}"} \
      ${GEMINI_API_KEY:+-e GEMINI_API_KEY="${GEMINI_API_KEY}"} \
      ${AI_MODEL:+-e KRR_AI_MODEL="${AI_MODEL}"} \
      ${AI_MAX_TOKENS:+-e KRR_AI_MAX_TOKENS="${AI_MAX_TOKENS}"} \
      ${OWNER_BATCH_SIZE:+-e KRR_OWNER_BATCH_SIZE="${OWNER_BATCH_SIZE}"} \
      -v $(pwd)/output:/output \
      "${DOCKER_IMAGE}" > "$TEMP_OUTPUT" 2>&1
    
    EXIT_CODE=$?
    
    # Display and log output
    cat "$TEMP_OUTPUT" | tee -a "$LOG_FILE"
    rm -f "$TEMP_OUTPUT"
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✓ Success: ${NS}${NC}" | tee -a "$LOG_FILE"
        SUCCESSES=$((SUCCESSES + 1))
    else
        echo -e "${RED}✗ Failed: ${NS} (exit code: ${EXIT_CODE})${NC}" | tee -a "$LOG_FILE"
        FAILURES=$((FAILURES + 1))
    fi
    
    echo "" | tee -a "$LOG_FILE"
done

# Summary
echo "" | tee -a "$LOG_FILE"
echo "==================================================" | tee -a "$LOG_FILE"
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}" | tee -a "$LOG_FILE"
echo -e "${GREEN}║                    SUMMARY                       ║${NC}" | tee -a "$LOG_FILE"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Total namespaces:  ${TOTAL}" | tee -a "$LOG_FILE"
echo -e "${GREEN}Successful:        ${SUCCESSES}${NC}" | tee -a "$LOG_FILE"

if [ $FAILURES -gt 0 ]; then
    echo -e "${RED}Failed:            ${FAILURES}${NC}" | tee -a "$LOG_FILE"
else
    echo "Failed:            0" | tee -a "$LOG_FILE"
fi

echo "" | tee -a "$LOG_FILE"
echo "Results: ./output/" | tee -a "$LOG_FILE"
echo "Log:     ${LOG_FILE}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✓ All namespaces analyzed successfully${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠ Some namespaces failed (${FAILURES}/${TOTAL})${NC}"
    exit 1
fi
