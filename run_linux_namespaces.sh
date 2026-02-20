#!/bin/bash

# Lista dei namespace Linux rilevanti
NAMESPACES=(
    "anthos-identity-service"
    "cert-manager"
    "default"
    "gke-connect"
    "gke-managed-metrics-server"
    "gke-system"
    "ingress-controller"
    "ml-prd"
    "monitoring"
    "qdrant-prd"
    "auditev-int-prd"
    "datev-svc-prd"
    "kube-system"
)

echo "Esecuzione test per ${#NAMESPACES[@]} namespace Linux..."
echo ""

for ns in "${NAMESPACES[@]}"; do
    echo "=================================================="
    echo "Processing namespace: $ns"
    echo "=================================================="
    ./test_gcp_quick.sh "$ns"
    echo ""
    echo "Completato: $ns"
    echo ""
done

echo "Tutti i namespace sono stati processati."
