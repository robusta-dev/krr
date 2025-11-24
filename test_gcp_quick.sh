#!/bin/bash
# Quick test script for KRR with GCP Managed Prometheus (single namespace)
#
# This script runs KRR on a single namespace to avoid rate limiting.
# Usage: ./test_gcp_quick.sh <namespace> [context] [use-anthos]
# Example: ./test_gcp_quick.sh gmp-test
# Example with context: ./test_gcp_quick.sh elyca-prd connectgateway_potent-bloom-361714_global_prd-user-cluster-01
# Example with Anthos: ./test_gcp_quick.sh elyca-prd "" anthos

set -e

HISTORY_DURATION="12"
TIMEFRAME_DURATION="1.25"

# Configuration
# Anthos cluster (use with: ./test_gcp_quick.sh namespace "" anthos)
# PROJECT_ID="potent-bloom-361714"
# CLUSTER_NAME="prd-user-cluster-01"
# USE_ANTHOS="anthos"
# CONTEXT="connectgateway_potent-bloom-361714_global_prd-user-cluster-01"

# GKE Cloud cluster (default)
PROJECT_ID="sicraweb-evo-dev"
CLUSTER_NAME="autopilot-cluster-sicra-dev"
USE_ANTHOS=""
#CONTEXT=""

LOCATION="global" # GCP Managed Prometheus location
NAMESPACE="${1:-default}"  # Default: default
# CONTEXT="${2:-}"  # Optional: Kubernetes context
# USE_ANTHOS="${3:-}"  # Optional: "anthos" to enable Anthos mode

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
echo ""

# Build context flag if provided
CONTEXT_FLAG=""
if [ -n "$CONTEXT" ]; then
    CONTEXT_FLAG="--context=${CONTEXT}"
fi

# Build Anthos flag if requested
ANTHOS_FLAG=""
if [ "$USE_ANTHOS" = "anthos" ]; then
    ANTHOS_FLAG="--gcp-anthos"
fi

# Run KRR with optimized parameters
$PYTHON_CMD krr.py simple \
  $CONTEXT_FLAG \
  --prometheus-url="${PROMETHEUS_URL}" \
  --prometheus-auth-header="Bearer ${TOKEN}" \
  --prometheus-cluster-label="${CLUSTER_NAME}" \
  --prometheus-label="cluster_name" \
  --namespace="${NAMESPACE}" \
  --history-duration="${HISTORY_DURATION}" \
  --timeframe-duration="${TIMEFRAME_DURATION}" \
  --cpu-percentile=95 \
  --memory-buffer-percentage=15 \
  $ANTHOS_FLAG \
  --show-cluster-name --fileoutput-dynamic

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Test completed${NC}"
else
    echo -e "${RED}✗ Test failed (exit code: ${EXIT_CODE})${NC}"
fi

exit $EXIT_CODE
