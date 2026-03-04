# AI-Assisted Strategy Guide

The AI-Assisted strategy leverages Large Language Models (LLMs) to analyze Prometheus metrics and provide intelligent resource recommendations for Kubernetes workloads.

## Overview

Unlike traditional rule-based algorithms, the AI-Assisted strategy:
- **Analyzes patterns and trends** in historical resource usage
- **Detects anomalies** like spikes and OOM kills
- **Considers context** such as HPA configuration and current allocations
- **Provides reasoning** for each recommendation with confidence scores
- **Adapts recommendations** based on workload characteristics

## Supported AI Providers

1. **OpenAI** (GPT-4, GPT-3.5, etc.)
2. **Google Gemini** (gemini-pro, gemini-1.5-pro)
3. **Anthropic Claude** (claude-3-opus, claude-3-sonnet, claude-3-haiku)
4. **Ollama** (local models: llama3, mistral, etc.)

## Quick Start

### 1. Set up your AI provider

**OpenAI:**
```bash
export OPENAI_API_KEY="sk-..."
```

**Google Gemini:**
```bash
export GEMINI_API_KEY="AI..."
```

**Anthropic Claude:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Ollama (local):**
```bash
# No API key needed, just ensure Ollama is running
ollama serve
```

### 2. Run KRR with AI strategy

```bash
# Auto-detect provider from environment
krr ai-assisted --namespace production

# Specify provider explicitly
krr ai-assisted --ai-provider openai --ai-model gpt-4 --namespace production

# Use compact mode to reduce token costs
krr ai-assisted --ai-compact-mode --namespace production
```

## Configuration Options

### AI Provider Settings

| Option | Description | Default |
|--------|-------------|---------|
| `--ai-provider` | AI provider (openai/gemini/anthropic/ollama) | Auto-detected |
| `--ai-model` | Model name (e.g., gpt-4, gemini-pro) | Provider default |
| `--ai-api-key` | API key (can also use env vars) | From env |
| `--ai-temperature` | Response randomness (0-2) | 0.3 |
| `--ai-max-tokens` | Maximum response tokens | 2000 |
| `--ai-timeout` | API call timeout (seconds) | 60 |

### Analysis Options

| Option | Description | Default |
|--------|-------------|---------|
| `--ai-compact-mode` | Compress prompts to reduce tokens (~60%) | False |
| `--ai-exclude-simple-reference` | Exclude Simple strategy baseline from AI prompt | False |
| `--use-oomkill-data` | Consider OOMKill events | True |
| `--history-duration` | Historical data duration (hours) | 336 (14 days) |

## Examples

### Basic Usage

```bash
# Run on all namespaces with default settings
export OPENAI_API_KEY="sk-..."
krr ai-assisted

# Run on specific namespace
krr ai-assisted --namespace production

# Output as JSON for automation
krr ai-assisted --namespace prod -f json > recommendations.json
```

### Cost Optimization

```bash
# Use compact mode to reduce API costs
krr ai-assisted --ai-compact-mode --namespace production

# Use a cheaper model
krr ai-assisted --ai-provider openai --ai-model gpt-3.5-turbo

# Use Ollama locally (no API costs)
krr ai-assisted --ai-provider ollama --ai-model llama3
```

### Custom Model Configuration

```bash
# Use GPT-4 for critical workloads
krr ai-assisted \
  --ai-provider openai \
  --ai-model gpt-4 \
  --ai-temperature 0.1 \
  --namespace critical-services

# Use Gemini Pro with higher creativity
krr ai-assisted \
  --ai-provider gemini \
  --ai-model gemini-1.5-pro \
  --ai-temperature 0.7

# Use Claude Opus for complex analysis
krr ai-assisted \
  --ai-provider anthropic \
  --ai-model claude-3-opus-20240229
```

### Local Analysis with Ollama

```bash
# Start Ollama server
ollama serve

# Pull a model (first time only)
ollama pull llama3

# Run KRR with local Ollama
krr ai-assisted \
  --ai-provider ollama \
  --ai-model llama3 \
  --namespace production
```

## Understanding the Output

The AI strategy provides recommendations with:

```
| Namespace | Name           | Container | CPU Request | CPU Limit | Memory Request | Memory Limit | Info                                                      |
|-----------|----------------|-----------|-------------|-----------|----------------|--------------|-----------------------------------------------------------|
| default   | nginx-deploy   | nginx     | 250m        | -         | 512Mi          | 512Mi        | AI: Based on p95 CPU at 0.18 cores with... (conf: 85%)  |
```

**Info field format:**
- `AI:` prefix indicates AI-generated recommendation
- Brief reasoning for the recommendation
- `(conf: XX%)` shows confidence level (0-100%)

**Confidence levels:**
- **80-100%**: High confidence, strong data support
- **50-79%**: Moderate confidence, some uncertainty
- **0-49%**: Low confidence, insufficient or inconsistent data

## Advanced Features

### Sanity Check Against Simple Strategy

The AI strategy compares its recommendations against the traditional "Simple" strategy:
- Logs warnings if recommendations deviate significantly (>50%)
- Helps catch unreasonable AI suggestions
- Can be excluded using `--ai-exclude-simple-reference` flag

### OOMKill Detection

When OOM kills are detected:
- AI prioritizes memory allocation in recommendations
- Significantly increases memory limits to prevent future kills
- Mentions OOMKills in reasoning

### HPA-Aware Recommendations

For workloads with HPA configured:
- Conservative CPU/Memory limits to allow autoscaling
- Considers target utilization percentages
- Mentions HPA in reasoning

### Retry Logic

Failed API calls are automatically retried:
- 3 attempts with exponential backoff
- Logs detailed error information
- Falls back to "undefined" recommendations on failure

## Cost Considerations

**Token Usage:**
- **Full mode**: ~1500-2000 tokens per workload
- **Compact mode**: ~600-800 tokens per workload
- **Response**: ~200-300 tokens

**Estimated Costs (per 100 workloads):**

| Provider | Model | Full Mode | Compact Mode |
|----------|-------|-----------|--------------|
| OpenAI | GPT-4 | ~$0.60 | ~$0.25 |
| OpenAI | GPT-3.5-turbo | ~$0.006 | ~$0.0025 |
| Gemini | gemini-pro | Free tier | Free tier |
| Anthropic | claude-3-opus | ~$0.45 | ~$0.20 |
| Ollama | llama3 | $0 (local) | $0 (local) |

## Troubleshooting

### API Key Not Found

```
Error: No AI provider API key found. Set OPENAI_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY
```

**Solution:** Export the appropriate API key:
```bash
export OPENAI_API_KEY="your-key-here"
```

### Rate Limit Exceeded

```
Error: Rate limit exceeded for API calls
```

**Solution:** 
- Add delays between runs
- Use `--max-workers 1` to serialize requests
- Switch to a higher tier API plan

### Low Confidence Scores

```
AI: Insufficient data for reliable... (conf: 30%)
```

**Solution:**
- Increase `--history-duration` to gather more data
- Ensure workloads have been running longer
- Check Prometheus data availability

### Ollama Connection Failed

```
Error: Failed to connect to Ollama at http://localhost:11434
```

**Solution:**
```bash
# Start Ollama server
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags
```

## Best Practices

1. **Start with compact mode** to minimize costs during testing
2. **Review AI reasoning** before applying recommendations to production
3. **Compare with Simple strategy** to validate reasonableness
4. **Use higher confidence threshold** for critical workloads
5. **Monitor actual resource usage** after applying recommendations
6. **Consider using Ollama** for frequent analysis to avoid API costs
7. **Set appropriate history duration** based on workload patterns

## Integration with CI/CD

```yaml
# Example GitHub Actions workflow
name: KRR AI Analysis
on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday 2 AM

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - name: Run KRR AI Analysis
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          krr ai-assisted \
            --ai-compact-mode \
            --namespace production \
            -f json \
            --fileoutput recommendations.json
      
      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: krr-recommendations
          path: recommendations.json
```

## Comparison with Other Strategies

| Feature | Simple | AI-Assisted |
|---------|--------|-------------|
| CPU Request | P95 percentile | Context-aware analysis |
| CPU Limit | Unset | Adaptive based on patterns |
| Memory Request | Max + 15% | Trend and spike-aware |
| Memory Limit | Max + 15% | OOMKill-aware |
| Reasoning | Fixed rules | Explained per workload |
| Cost | Free | API costs (or free with Ollama) |
| Accuracy | Good baseline | Potentially better with context |

## Feedback and Improvements

The AI strategy learns from:
- Historical usage patterns
- Workload configuration (HPA, current allocations)
- Kubernetes events (OOMKills)
- Reference algorithms (Simple strategy)

To improve recommendations:
1. Ensure Prometheus has quality historical data
2. Configure HPAs properly if using autoscaling
3. Review and adjust `--history-duration` for workload patterns
4. Experiment with different AI models and temperatures
