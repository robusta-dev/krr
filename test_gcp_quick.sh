#!/bin/bash
# Script di test rapido per KRR con GCP Managed Prometheus (singolo namespace)
#
# Questo script esegue KRR su un singolo namespace per evitare rate limiting.
# Uso: ./test_gcp_quick.sh <namespace>
# Esempio: ./test_gcp_quick.sh gmp-test

set -e

# Configurazione
PROJECT_ID="potent-bloom-361714"
CLUSTER_NAME="prd-user-cluster-01"
LOCATION="global"
NAMESPACE="${1:-gmp-test}"  # Default: gmp-test

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}KRR GCP Quick Test (Namespace: ${NAMESPACE})${NC}"
echo "=================================================="
echo ""

# Verifica Python
PYTHON_CMD=$(command -v python3 || command -v python)

# Ottieni token
echo -e "${YELLOW}Ottenendo token GCP...${NC}"
TOKEN=$(gcloud auth print-access-token 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo -e "${RED}Errore: Token non disponibile${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Token ottenuto${NC}"
echo ""

# URL Prometheus
PROMETHEUS_URL="https://monitoring.googleapis.com/v1/projects/${PROJECT_ID}/location/${LOCATION}/prometheus"

echo "Analizzando namespace: ${NAMESPACE}"
echo "Cluster: ${CLUSTER_NAME}"
echo ""

# Esegui KRR con parametri ottimizzati
$PYTHON_CMD krr.py simple \
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
    echo -e "${GREEN}✓ Test completato${NC}"
else
    echo -e "${RED}✗ Test fallito (exit code: ${EXIT_CODE})${NC}"
fi

exit $EXIT_CODE
