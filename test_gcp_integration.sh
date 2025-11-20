#!/bin/bash
# Script di test per KRR con GCP Managed Prometheus
#
# Questo script esegue KRR con GCP Managed Prometheus per il cluster autopilot-cluster-sicra-dev
# nel progetto sicraweb-evo-dev.
#
# Assicurati di avere:
# 1. gcloud CLI installato e configurato
# 2. Accesso al progetto GCP
# 3. Managed Service for Prometheus abilitato
# 4. Python environment con KRR installato

set -e  # Exit on error

# Configurazione
PROJECT_ID="sicraweb-evo-dev"
CLUSTER_NAME="sicraweb-next"
LOCATION="global"

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}KRR GCP Managed Prometheus Test Script${NC}"
echo "========================================"
echo ""

# Verifica prerequisiti
echo -e "${YELLOW}Verificando prerequisiti...${NC}"

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Errore: gcloud CLI non trovato${NC}"
    echo "Installa gcloud CLI da: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo -e "${RED}Errore: Python non trovato${NC}"
    exit 1
fi

PYTHON_CMD=$(command -v python3 || command -v python)

echo -e "${GREEN}✓ Prerequisiti verificati${NC}"
echo ""

# Ottieni token di autenticazione
echo -e "${YELLOW}Ottenendo token di autenticazione GCP...${NC}"
TOKEN=$(gcloud auth print-access-token 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo -e "${RED}Errore: Impossibile ottenere il token di autenticazione${NC}"
    echo "Esegui: gcloud auth login"
    exit 1
fi

echo -e "${GREEN}✓ Token ottenuto${NC}"
echo ""

# Costruisci URL Prometheus
PROMETHEUS_URL="https://monitoring.googleapis.com/v1/projects/${PROJECT_ID}/location/${LOCATION}/prometheus"

echo "Configurazione:"
echo "  Project ID: ${PROJECT_ID}"
echo "  Cluster: ${CLUSTER_NAME}"
echo "  Prometheus URL: ${PROMETHEUS_URL}"
echo ""

# Test connessione (query semplice)
echo -e "${YELLOW}Testando connessione a GCP Managed Prometheus...${NC}"
TEST_QUERY='up'
CURL_RESPONSE=$(curl -s -w "%{http_code}" -o /tmp/gcp_test_response.txt \
  -H "Authorization: Bearer $TOKEN" \
  "${PROMETHEUS_URL}/api/v1/query?query=${TEST_QUERY}")

HTTP_CODE="${CURL_RESPONSE: -3}"

if [ "$HTTP_CODE" != "200" ]; then
    echo -e "${RED}Errore: Connessione fallita (HTTP ${HTTP_CODE})${NC}"
    echo "Risposta:"
    cat /tmp/gcp_test_response.txt
    exit 1
fi

echo -e "${GREEN}✓ Connessione a Prometheus riuscita${NC}"
echo ""

# Esegui KRR
echo -e "${YELLOW}Eseguendo KRR con strategia 'simple'...${NC}"
echo ""
echo "NOTA: Parametri ottimizzati per evitare rate limiting GCP (180 req/min)"
echo "  --history-duration=3 ore (ridotto da 12)"
echo "  --timeframe-duration=5 minuti (aumentato da 1.25)"
echo ""
echo "Per testare un namespace specifico, aggiungi: --namespace=<nome>"
echo "Esempio: $0 --namespace=gmp-test"
echo ""

# Passa tutti gli argomenti aggiuntivi dello script a KRR
$PYTHON_CMD krr.py simple \
  --prometheus-url="${PROMETHEUS_URL}" \
  --prometheus-auth-header="Bearer ${TOKEN}" \
  --prometheus-cluster-label="${CLUSTER_NAME}" \
  --prometheus-label="cluster_name" \
  --history-duration=3 \
  --timeframe-duration=5 \
  --cpu-percentile=95 \
  --memory-buffer-percentage=15 \
  "$@"

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ KRR eseguito con successo${NC}"
else
    echo -e "${RED}✗ KRR terminato con errori (exit code: ${EXIT_CODE})${NC}"
fi

exit $EXIT_CODE
