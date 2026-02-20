#!/bin/bash
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Load configuration from .env
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Create a .env file with PROJECT_ID, CLUSTER_NAME, etc."
    exit 1
fi

set -a
source .env
set +a

# Parameters (can be overridden via command line)
NAMESPACE="${1:-${NAMESPACE:-default}}"
STRATEGY="${2:-simple}"  # simple, simple-limit, ai-assisted

# Validate required variables
if [ -z "${PROJECT_ID}" ] || [ -z "${CLUSTER_NAME}" ]; then
    echo -e "${RED}Error: PROJECT_ID and CLUSTER_NAME must be set in .env${NC}"
    exit 1
fi

echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          KRR Docker Runner (from .env)           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "Project:    ${PROJECT_ID}"
echo "Cluster:    ${CLUSTER_NAME}"
echo "Namespace:  ${NAMESPACE}"
echo "Strategy:   ${STRATEGY}"
echo "Context:    ${CONTEXT:-auto}"
echo "Mode:       $([ "$USE_ANTHOS" = "anthos" ] && echo "Anthos (on-prem)" || echo "GKE Cloud")"
echo "AI Mode:    ${AI_MODE:-false}"
echo "HPA Mode:   ${HPA_MODE:-false}"
echo ""

# Get GCP token automatically
echo -e "${YELLOW}→ Getting GCP access token...${NC}"
TOKEN=$(gcloud auth print-access-token 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo -e "${RED}✗ Failed to get GCP token${NC}"
    echo "Run: gcloud auth login"
    exit 1
fi

echo -e "${GREEN}✓ Token obtained${NC}"

# Convert USE_ANTHOS from "anthos" to "true" for Docker
if [ "${USE_ANTHOS}" = "anthos" ]; then
    GCP_ANTHOS_VALUE="true"
else
    GCP_ANTHOS_VALUE="false"
fi

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
        echo -e "${YELLOW}→ Building Docker image (first run)...${NC}"
        docker build -f Dockerfile.gcloud -t "${DOCKER_IMAGE}" .
        echo -e "${GREEN}✓ Image built${NC}"
    else
        echo -e "${GREEN}✓ Image ready${NC}"
    fi
fi

# Create output directory
mkdir -p ./output

echo ""
echo -e "${YELLOW}→ Starting KRR analysis...${NC}"
echo ""

# Determine strategy based on AI_MODE
if [ "${AI_MODE}" = "true" ]; then
    ACTUAL_STRATEGY="ai-assisted"
    echo -e "${GREEN}Using AI-assisted strategy with ${AI_MODEL:-gemini-3-flash-preview}${NC}"
else
    ACTUAL_STRATEGY="${STRATEGY}"
    echo -e "${GREEN}Using ${STRATEGY} strategy${NC}"
fi

# Run Docker container with all environment variables from .env
docker run --rm \
  -v "${HOME}/.kube/config:/root/.kube/config:ro" \
  -e CLOUDSDK_AUTH_ACCESS_TOKEN="${TOKEN}" \
  -e KRR_STRATEGY="${ACTUAL_STRATEGY}" \
  -e KRR_PROMETHEUS_URL="https://monitoring.googleapis.com/v1/projects/${PROJECT_ID}/location/global/prometheus" \
  -e KRR_PROMETHEUS_AUTH_HEADER="Bearer ${TOKEN}" \
  -e KRR_PROMETHEUS_CLUSTER_LABEL="${CLUSTER_NAME}" \
  -e KRR_PROMETHEUS_LABEL="cluster_name" \
  ${CONTEXT:+-e KRR_CONTEXT="${CONTEXT}"} \
  -e KRR_NAMESPACE="${NAMESPACE}" \
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
  "${DOCKER_IMAGE}"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              ✓ Analysis completed               ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Results saved to: ./output/"
    echo ""
    ls -lh output/krr-*.table 2>/dev/null | tail -3 || true
else
    echo -e "${RED}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║          ✗ Analysis failed (code: $EXIT_CODE)           ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════════════════╝${NC}"
fi

exit $EXIT_CODE
