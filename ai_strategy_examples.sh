#!/bin/bash
# Example: Using AI-Assisted strategy with different providers and GCP Prometheus

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}===================================================${NC}"
echo -e "${GREEN}KRR AI-Assisted Strategy Examples${NC}"
echo -e "${GREEN}===================================================${NC}"
echo ""

# Check if required tools are installed
command -v python >/dev/null 2>&1 || { echo "❌ python not found."; exit 1; }
source .env 2>/dev/null || echo -e "${YELLOW}⚠️  .env file not found, proceeding with environment variables only.${NC}"

echo "📋 Available Examples:"
echo "  1. OpenAI GPT-4"
echo "  2. OpenAI GPT-3.5-turbo (cost-effective)"
echo "  3. Google Gemini Pro (free tier)"
echo "  4. Anthropic Claude"
echo "  5. Ollama (local, no API costs)"
echo "  6. Compact mode (reduced token usage)"
echo "  7. GCP/Anthos Prometheus with AI-Assisted"
echo "  8. Compare AI vs Simple strategy"
echo ""

# Function to check environment variable
check_env() {
    if [ -z "${!1}" ]; then
        echo "❌ $1 environment variable not set"
        return 1
    else
        echo "✅ $1 is set"
        return 0
    fi
}

# Example 1: OpenAI GPT-4
example_openai_gpt4() {
    echo ""
    echo "==================================================="
    echo "Example 1: OpenAI GPT-4 (High Quality)"
    echo "==================================================="
    
    if ! check_env OPENAI_API_KEY; then
        echo "To use this example:"
        echo "  export OPENAI_API_KEY=\"sk-...\""
        return
    fi
    
    echo ""
    echo "Running KRR with GPT-4..."
    echo "Command:"
    echo "  krr ai-assisted --ai-provider openai --ai-model gpt-4 --namespace default"
    echo ""
    
    krr ai-assisted \
        --ai-provider openai \
        --ai-model gpt-4 \
        --ai-temperature 0.2 \
        --namespace default \
        -f table \
        --quiet
}

# Example 2: OpenAI GPT-3.5-turbo (cost-effective)
example_openai_gpt35() {
    echo ""
    echo "==================================================="
    echo "Example 2: OpenAI GPT-3.5-turbo (Cost-Effective)"
    echo "==================================================="
    
    if ! check_env OPENAI_API_KEY; then
        echo "To use this example:"
        echo "  export OPENAI_API_KEY=\"sk-...\""
        return
    fi
    
    echo ""
    echo "Running KRR with GPT-3.5-turbo..."
    echo "Command:"
    echo "  krr ai-assisted --ai-provider openai --ai-model gpt-3.5-turbo --ai-compact-mode -n default"
    echo ""
    
    krr ai-assisted \
        --ai-provider openai \
        --ai-model gpt-3.5-turbo \
        --ai-compact-mode \
        --namespace default \
        -f table \
        --quiet
}

# Example 3: Google Gemini Pro
example_gemini() {
    echo ""
    echo "==================================================="
    echo "Example 3: Google Gemini Pro (Free Tier)"
    echo "==================================================="
    
    if ! check_env GEMINI_API_KEY; then
        echo "To use this example:"
        echo "  1. Get API key from https://makersuite.google.com/app/apikey"
        echo "  2. export GEMINI_API_KEY=\"AI...\""
        return
    fi
    
    echo ""
    echo "Running KRR with Gemini Pro..."
    echo "Command:"
    echo "  krr ai-assisted --ai-provider gemini --ai-model gemini-pro -n default"
    echo ""
    
    krr ai-assisted \
        --ai-provider gemini \
        --ai-model gemini-pro \
        --namespace default \
        -f table \
        --quiet
}

# Example 4: Anthropic Claude
example_anthropic() {
    echo ""
    echo "==================================================="
    echo "Example 4: Anthropic Claude 3 Sonnet"
    echo "==================================================="
    
    if ! check_env ANTHROPIC_API_KEY; then
        echo "To use this example:"
        echo "  export ANTHROPIC_API_KEY=\"sk-ant-...\""
        return
    fi
    
    echo ""
    echo "Running KRR with Claude 3 Sonnet..."
    echo "Command:"
    echo "  krr ai-assisted --ai-provider anthropic --ai-model claude-3-sonnet-20240229 -n default"
    echo ""
    
    krr ai-assisted \
        --ai-provider anthropic \
        --ai-model claude-3-sonnet-20240229 \
        --namespace default \
        -f table \
        --quiet
}

# Example 5: Ollama (local)
example_ollama() {
    echo ""
    echo "==================================================="
    echo "Example 5: Ollama (Local, No API Costs)"
    echo "==================================================="
    
    # Check if Ollama is running
    if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "❌ Ollama is not running"
        echo ""
        echo "To use this example:"
        echo "  1. Install Ollama: https://ollama.ai/"
        echo "  2. Start Ollama: ollama serve"
        echo "  3. Pull a model: ollama pull llama3"
        return
    fi
    
    echo "✅ Ollama is running"
    echo ""
    echo "Running KRR with Ollama (llama3)..."
    echo "Command:"
    echo "  krr ai-assisted --ai-provider ollama --ai-model llama3 -n default"
    echo ""
    
    krr ai-assisted \
        --ai-provider ollama \
        --ai-model llama3 \
        --namespace default \
        -f table \
        --quiet
}

# Example 6: Compact mode comparison
example_compact_mode() {
    echo ""
    echo "==================================================="
    echo "Example 6: Compact Mode (Token Usage Reduction)"
    echo "==================================================="
    
    if ! check_env OPENAI_API_KEY; then
        echo "Skipping (OPENAI_API_KEY not set)"
        return
    fi
    
    echo ""
    echo "Running KRR in FULL mode..."
    echo "Command:"
    echo "  krr ai-assisted --ai-provider openai -n default"
    echo ""
    
    time krr ai-assisted \
        --ai-provider openai \
        --ai-model gpt-3.5-turbo \
        --namespace default \
        -f table \
        --quiet
    
    echo ""
    echo "Running KRR in COMPACT mode..."
    echo "Command:"
    echo "  krr ai-assisted --ai-provider openai --ai-compact-mode -n default"
    echo ""
    
    time krr ai-assisted \
        --ai-provider openai \
        --ai-model gpt-3.5-turbo \
        --ai-compact-mode \
        --namespace default \
        -f table \
        --quiet
    
    echo ""
    echo "💡 Compact mode reduces token usage by ~60%"
}

# Example 7: GCP/Anthos with AI-Assisted strategy
example_gcp_prometheus() {
    echo ""
    echo -e "${GREEN}===================================================${NC}"
    echo -e "${GREEN}Example 7: GCP/Anthos Prometheus with AI-Assisted${NC}"
    echo -e "${GREEN}===================================================${NC}"
    
    # Check for GCP configuration
    if [ -z "${PROJECT_ID:-}" ] || [ -z "${CLUSTER_NAME:-}" ]; then
        echo -e "${YELLOW}GCP configuration not found in environment${NC}"
        echo ""
        echo "To use this example, set:"
        echo "  export PROJECT_ID=\"your-project-id\""
        echo "  export CLUSTER_NAME=\"your-cluster-name\""
        echo "  export LOCATION=\"global\"  # optional, default: global"
        echo "  export CONTEXT=\"gke_PROJECT_LOCATION_CLUSTER\"  # optional"
        echo ""
        echo "For Anthos clusters, use:"
        echo "  export CONTEXT=\"connectgateway_PROJECT_LOCATION_CLUSTER\""
        echo "  export USE_ANTHOS=\"anthos\""
        return
    fi
    
    # Auto-detect cluster type from CONTEXT if set
    CLUSTER_TYPE="GKE"
    ANTHOS_FLAG=""
    
    if [ -n "${CONTEXT:-}" ]; then
        if [[ "$CONTEXT" == connectgateway_* ]]; then
            CLUSTER_TYPE="Anthos"
            ANTHOS_FLAG="--gcp-anthos"
            # Extract from connectgateway_PROJECT_LOCATION_CLUSTERNAME
            DETECTED_PROJECT=$(echo "$CONTEXT" | cut -d'_' -f2)
            DETECTED_CLUSTER=$(echo "$CONTEXT" | cut -d'_' -f4)
            PROJECT_ID="${DETECTED_PROJECT:-$PROJECT_ID}"
            CLUSTER_NAME="${DETECTED_CLUSTER:-$CLUSTER_NAME}"
        elif [[ "$CONTEXT" == gke_* ]]; then
            CLUSTER_TYPE="GKE"
            # Extract from gke_PROJECT_LOCATION_CLUSTERNAME
            DETECTED_PROJECT=$(echo "$CONTEXT" | cut -d'_' -f2)
            DETECTED_CLUSTER=$(echo "$CONTEXT" | cut -d'_' -f4)
            PROJECT_ID="${DETECTED_PROJECT:-$PROJECT_ID}"
            CLUSTER_NAME="${DETECTED_CLUSTER:-$CLUSTER_NAME}"
        fi
    fi
    
    # Check for AI provider
    if ! check_env OPENAI_API_KEY && ! check_env GEMINI_API_KEY && \
       ! check_env ANTHROPIC_API_KEY && [ "${AI_PROVIDER:-}" != "ollama" ]; then
        echo -e "${RED}No AI API key found${NC}"
        echo "Set one of: OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY"
        return
    fi
    
    # Set defaults
    LOCATION="${LOCATION:-global}"
    HISTORY_DURATION="${HISTORY_DURATION:-300}"
    TIMEFRAME_DURATION="${TIMEFRAME_DURATION:-1.25}"
    CPU_PERCENTILE="${CPU_PERCENTILE:-95}"
    TARGET_NAMESPACE="${NAMESPACE:-default}"
    
    echo ""
    echo -e "${BLUE}Configuration:${NC}"
    echo "  Cluster Type: ${CLUSTER_TYPE}"
    echo "  PROJECT_ID: ${PROJECT_ID}"
    echo "  CLUSTER_NAME: ${CLUSTER_NAME}"
    echo "  LOCATION: ${LOCATION}"
    echo "  NAMESPACE: ${TARGET_NAMESPACE}"
    if [ -n "$CONTEXT" ]; then
        echo "  CONTEXT: ${CONTEXT}"
    fi
    
    # Get GCP access token
    echo ""
    echo -e "${YELLOW}Getting GCP access token...${NC}"
    TOKEN=$(gcloud auth print-access-token 2>/dev/null)
    
    if [ -z "$TOKEN" ]; then
        echo -e "${RED}ERROR: Cannot get GCP token${NC}"
        echo "Run: gcloud auth login"
        return
    fi
    
    echo -e "${GREEN}✓ Token obtained${NC}"
    
    # Build Prometheus URL
    PROMETHEUS_URL="https://monitoring.googleapis.com/v1/projects/${PROJECT_ID}/location/${LOCATION}/prometheus"
    
    echo ""
    echo -e "${YELLOW}Running KRR AI-Assisted with GCP Prometheus...${NC}"
    echo "Command:"
    echo "  python krr.py ai-assisted \\"
    echo "    --prometheus-url=\"${PROMETHEUS_URL}\" \\"
    echo "    --prometheus-auth-header=\"Bearer \$TOKEN\" \\"
    echo "    --prometheus-cluster-label=\"${CLUSTER_NAME}\" \\"
    echo "    --prometheus-label=\"cluster_name\" \\"
    echo "    --namespace=\"${TARGET_NAMESPACE}\" \\"
    echo "    --history-duration=\"${HISTORY_DURATION}\" \\"
    echo "    --ai-compact-mode \\"
    if [ -n "$CONTEXT" ]; then
        echo "    --context=\"${CONTEXT}\" \\"
    fi
    echo "    ${ANTHOS_FLAG}"
    echo ""
    
    # Run KRR with AI strategy
    python krr.py ai-assisted \
        ${CONTEXT:+--context="${CONTEXT}"} \
        --prometheus-url="${PROMETHEUS_URL}" \
        --prometheus-auth-header="Bearer ${TOKEN}" \
        --prometheus-cluster-label="${CLUSTER_NAME}" \
        --prometheus-label="cluster_name" \
        --namespace="${TARGET_NAMESPACE}" \
        --history-duration="${HISTORY_DURATION}" \
        --timeframe-duration="${TIMEFRAME_DURATION}" \
        --cpu-percentile="${CPU_PERCENTILE}" \
        --memory-buffer-percentage=15 \
        ${ANTHOS_FLAG} \
        -f table # --ai-exclude-simple-reference
    
    EXIT_CODE=$?
    
    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✓ AI-Assisted analysis completed${NC}"
    else
        echo -e "${RED}✗ AI-Assisted analysis failed (exit code: ${EXIT_CODE})${NC}"
    fi
}

# Example 8: Compare AI vs Simple strategy on GCP
example_comparison() {
    echo ""
    echo -e "${GREEN}===================================================${NC}"
    echo -e "${GREEN}Example 8: AI vs Simple Strategy Comparison${NC}"
    echo -e "${GREEN}===================================================${NC}"
    
    echo ""
    echo -e "${YELLOW}Running Simple strategy...${NC}"
    echo "Command:"
    echo "  python krr.py simple -n default"
    echo ""
    
    python krr.py simple --namespace default -f table --quiet > /tmp/krr-simple.txt 2>&1
    cat /tmp/krr-simple.txt
    
    if check_env OPENAI_API_KEY || check_env GEMINI_API_KEY || check_env ANTHROPIC_API_KEY; then
        echo ""
        echo -e "${YELLOW}Running AI-Assisted strategy...${NC}"
        echo "Command:"
        echo "  python krr.py ai-assisted --ai-compact-mode -n default"
        echo ""
        
        python krr.py ai-assisted \
            --ai-compact-mode \
            --namespace default \
            -f table \
            --quiet > /tmp/krr-ai.txt 2>&1
        cat /tmp/krr-ai.txt
        
        echo ""
        echo -e "${BLUE}💡 Compare the recommendations:${NC}"
        echo "   - Simple uses P95 CPU and Max Memory + 15%"
        echo "   - AI considers trends, spikes, OOMKills, and HPA"
    else
        echo -e "${YELLOW}Skipping AI comparison (no API key set)${NC}"
    fi
}

# Parse command line arguments
if [ $# -eq 0 ]; then
    # Run all examples that have required environment variables
    [ -n "$OPENAI_API_KEY" ] && example_openai_gpt35
    [ -n "$GEMINI_API_KEY" ] && example_gemini
    [ -n "$ANTHROPIC_API_KEY" ] && example_anthropic
    command -v ollama >/dev/null 2>&1 && example_ollama
else
    case "$1" in
        1|openai|gpt4)
            example_openai_gpt4
            ;;
        2|gpt35|cost)
            example_openai_gpt35
            ;;
        3|gemini|free)
            example_gemini
            ;;
        4|anthropic|claude)
            example_anthropic
            ;;
        5|ollama|local)
            example_ollama
            ;;
        6|compact)
            example_compact_mode
            ;;
        7|gcp|anthos|prometheus)
            example_gcp_prometheus
            ;;
        8|compare|comparison)
            example_comparison
            ;;
        all)
            example_openai_gpt4
            example_openai_gpt35
            example_gemini
            example_anthropic
            example_ollama
            example_compact_mode
            example_gcp_prometheus
            example_comparison
            ;;
        *)
            echo "Usage: $0 [example_number|all]"
            echo ""
            echo "Examples:"
            echo "  $0 1          # OpenAI GPT-4"
            echo "  $0 2          # OpenAI GPT-3.5-turbo"
            echo "  $0 3          # Google Gemini Pro"
            echo "  $0 4          # Anthropic Claude"
            echo "  $0 5          # Ollama (local)"
            echo "  $0 6          # Compact mode comparison"
            echo "  $0 7          # GCP/Anthos Prometheus"
            echo "  $0 8          # AI vs Simple comparison"
            echo "  $0 all        # Run all examples"
            echo "  $0            # Run examples with available API keys"
            exit 1
            ;;
    esac
fi

echo ""
echo "==================================================="
echo "✅ Examples completed!"
echo "==================================================="
