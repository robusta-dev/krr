#!/bin/bash
# Quick test script for KRR with GCP Managed Prometheus (single namespace)
#
# This script runs KRR on a single namespace to avoid rate limiting.
# Usage: ./test_gcp_quick.sh <namespace> [context]
# Example: ./test_gcp_quick.sh gmp-test
# Example with context: ./test_gcp_quick.sh elyca-prd connectgateway_potent-bloom-361714_global_prd-user-cluster-01

set -e

# Configuration
PROJECT_ID="potent-bloom-361714"
CLUSTER_NAME="prd-user-cluster-01"
LOCATION="global" # GCP Managed Prometheus location (default: usually global)
NAMESPACE="${1:-gmp-test}"  # Default: gmp-test
CONTEXT="${2:-}"  # Optional: Kubernetes context

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
echo ""

# Build context flag if provided
CONTEXT_FLAG=""
if [ -n "$CONTEXT" ]; then
    CONTEXT_FLAG="--context=${CONTEXT}"
fi

# Run KRR with optimized parameters
$PYTHON_CMD krr.py simple \
  $CONTEXT_FLAG \
  --prometheus-url="${PROMETHEUS_URL}" \
  --prometheus-auth-header="Bearer ${TOKEN}" \
  --prometheus-cluster-label="${CLUSTER_NAME}" \
  --prometheus-label="cluster_name" \
  --namespace="${NAMESPACE}" \
  --history-duration=12 \
  --timeframe-duration=5 \
  --cpu-percentile=95 \
  --memory-buffer-percentage=15 \
  --gcp-anthos

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Test completed${NC}"
else
    echo -e "${RED}✗ Test failed (exit code: ${EXIT_CODE})${NC}"
fi

exit $EXIT_CODE
