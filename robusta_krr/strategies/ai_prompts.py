"""AI prompt generation and statistics extraction for resource recommendations."""

import logging
from typing import TYPE_CHECKING, Union

import numpy as np

from robusta_krr.core.abstract.strategies import MetricsPodData
from robusta_krr.core.models.objects import K8sObjectData

if TYPE_CHECKING:
    from robusta_krr.strategies.ai_assisted import AiAssistedStrategySettings

logger = logging.getLogger("krr")


def extract_comprehensive_stats(
    history_data: MetricsPodData, 
    object_data: K8sObjectData
) -> dict:
    """Extract comprehensive statistics from Prometheus metrics data.
    
    This function analyzes the historical data and extracts:
    - CPU statistics (percentiles, mean, std, trend, spikes)
    - Memory statistics (max, mean, std, OOMKills)
    - Pod information (count, names, health)
    - Workload context (HPA, allocations, labels)
    - Temporal context (duration, data points)
    
    Args:
        history_data: Dictionary of metric loaders -> pod data
        object_data: Kubernetes object metadata
        
    Returns:
        Dictionary with comprehensive statistics
    """
    stats = {
        "workload": {
            "namespace": object_data.namespace,
            "name": object_data.name,
            "kind": object_data.kind,
            "container": object_data.container,
        },
        "pods": {
            "current_count": object_data.current_pods_count,
            "deleted_count": object_data.deleted_pods_count,
            "total_count": object_data.pods_count,
            "names": [pod.name for pod in object_data.pods if not pod.deleted][:5],  # First 5
        },
        "cpu": {},
        "memory": {},
        "allocations": {},
        "hpa": None,
        "warnings": list(object_data.warnings),
        "temporal": {},
    }
    
    # Extract CPU statistics
    if "PercentileCPULoader" in history_data or "CPULoader" in history_data:
        cpu_data_key = "PercentileCPULoader" if "PercentileCPULoader" in history_data else "CPULoader"
        cpu_data = history_data.get(cpu_data_key, {})
        
        if cpu_data:
            # Collect all CPU values across all pods
            all_cpu_values = []
            per_pod_stats = {}
            
            for pod_name, values in cpu_data.items():
                if len(values) > 0:
                    cpu_values = values[:, 1]  # Extract values (second column)
                    all_cpu_values.extend(cpu_values)
                    
                    # Per-pod statistics
                    per_pod_stats[pod_name] = {
                        "max": float(np.max(cpu_values)),
                        "mean": float(np.mean(cpu_values)),
                        "std": float(np.std(cpu_values)),
                    }
            
            if all_cpu_values:
                all_cpu_array = np.array(all_cpu_values)
                
                # Calculate percentiles
                percentiles = [50, 75, 90, 95, 99]
                percentile_values = {
                    f"p{p}": float(np.percentile(all_cpu_array, p))
                    for p in percentiles
                }
                
                # Calculate trend (linear regression slope)
                try:
                    # Use timestamps and values from first pod for trend
                    first_pod_data = list(cpu_data.values())[0]
                    if len(first_pod_data) > 1:
                        timestamps = first_pod_data[:, 0]
                        values = first_pod_data[:, 1]
                        # Normalize timestamps to start from 0
                        t_norm = timestamps - timestamps[0]
                        # Linear fit: y = slope * x + intercept
                        slope, _ = np.polyfit(t_norm, values, 1)
                        trend_slope = float(slope)
                    else:
                        trend_slope = 0.0
                except Exception as e:
                    logger.debug(f"Failed to calculate CPU trend: {e}")
                    trend_slope = 0.0
                
                # Count spikes (values > 2x mean)
                mean_cpu = np.mean(all_cpu_array)
                spike_count = int(np.sum(all_cpu_array > 2 * mean_cpu))
                
                stats["cpu"] = {
                    "percentiles": percentile_values,
                    "max": float(np.max(all_cpu_array)),
                    "mean": float(mean_cpu),
                    "std": float(np.std(all_cpu_array)),
                    "trend_slope": trend_slope,
                    "spike_count": spike_count,
                    "per_pod": per_pod_stats,
                }
    
    # Extract CPU data points count
    if "CPUAmountLoader" in history_data:
        cpu_amount_data = history_data["CPUAmountLoader"]
        total_points = sum(
            values[0, 1] for values in cpu_amount_data.values() if len(values) > 0
        )
        stats["temporal"]["cpu_data_points"] = int(total_points)
    
    # Extract Memory statistics
    if "MaxMemoryLoader" in history_data:
        memory_data = history_data["MaxMemoryLoader"]
        
        if memory_data:
            per_pod_memory = {}
            all_max_memory = []
            
            for pod_name, values in memory_data.items():
                if len(values) > 0:
                    memory_values = values[:, 1]
                    pod_max = float(np.max(memory_values))
                    all_max_memory.append(pod_max)
                    
                    per_pod_memory[pod_name] = {
                        "max": pod_max,
                        "mean": float(np.mean(memory_values)),
                        "std": float(np.std(memory_values)),
                    }
            
            if all_max_memory:
                stats["memory"] = {
                    "max": float(np.max(all_max_memory)),
                    "mean": float(np.mean(all_max_memory)),
                    "std": float(np.std(all_max_memory)),
                    "per_pod": per_pod_memory,
                }
    
    # Extract Memory data points count
    if "MemoryAmountLoader" in history_data:
        memory_amount_data = history_data["MemoryAmountLoader"]
        total_points = sum(
            values[0, 1] for values in memory_amount_data.values() if len(values) > 0
        )
        stats["temporal"]["memory_data_points"] = int(total_points)
    
    # Extract OOMKill information
    oomkill_detected = False
    if "MaxOOMKilledMemoryLoader" in history_data:
        oomkill_data = history_data["MaxOOMKilledMemoryLoader"]
        if oomkill_data:
            max_oomkill_value = max(
                (values[0, 1] for values in oomkill_data.values() if len(values) > 0),
                default=0
            )
            if max_oomkill_value > 0:
                oomkill_detected = True
                stats["memory"]["oomkill_detected"] = True
                stats["memory"]["oomkill_max_value"] = float(max_oomkill_value)
    
    if not oomkill_detected:
        stats["memory"]["oomkill_detected"] = False
    
    # Extract current allocations
    if object_data.allocations:
        stats["allocations"] = {
            "cpu": {
                "request": object_data.allocations.requests.get("cpu"),
                "limit": object_data.allocations.limits.get("cpu"),
            },
            "memory": {
                "request": object_data.allocations.requests.get("memory"),
                "limit": object_data.allocations.limits.get("memory"),
            },
        }
    
    # Extract HPA information
    if object_data.hpa:
        stats["hpa"] = {
            "min_replicas": object_data.hpa.min_replicas,
            "max_replicas": object_data.hpa.max_replicas,
            "current_replicas": object_data.hpa.current_replicas,
            "target_cpu_utilization": object_data.hpa.target_cpu_utilization_percentage,
            "target_memory_utilization": object_data.hpa.target_memory_utilization_percentage,
        }
    
    # Calculate total data points
    cpu_points = stats.get("temporal", {}).get("cpu_data_points", 0)
    memory_points = stats.get("temporal", {}).get("memory_data_points", 0)
    stats["temporal"]["total_data_points"] = cpu_points + memory_points
    
    return stats


def get_system_prompt(provider: str, include_simple_ref: bool = True) -> str:
    """Get the system prompt with instructions for the AI.
    
    Args:
        provider: AI provider name
        include_simple_ref: Whether to include Simple strategy algorithm reference
        
    Returns:
        System prompt string
    """
    simple_reference = ""
    if include_simple_ref:
        simple_reference = """
## Reference: Simple Strategy Algorithm

For comparison, the standard "Simple" strategy uses:
- **CPU Request**: 95th percentile of historical usage, Limit: unset
- **Memory Request & Limit**: Max usage + 15% buffer

You can use this as a baseline, but feel free to deviate if you detect patterns
that warrant different recommendations (e.g., high variance, clear trends, spikes).
"""
    
    prompt = f"""You are an expert Kubernetes resource optimization system. Your task is to analyze 
historical resource usage metrics from Prometheus and provide optimized CPU and Memory 
resource recommendations for Kubernetes workloads.

## Your Goal

Analyze the provided statistics and recommend appropriate:
- CPU request (in cores, can be fractional like 0.5)
- CPU limit (in cores, or null for no limit)
- Memory request (in bytes)
- Memory limit (in bytes)

## Analysis Approach

Consider these factors:
1. **Usage Patterns**: Percentiles, mean, standard deviation
2. **Trends**: Is usage increasing, decreasing, or stable? (check trend_slope)
3. **Spikes**: Are there sudden usage spikes? (check spike_count)
4. **OOM Kills**: Has the container been killed for out-of-memory?
5. **Current Allocations**: Are current requests/limits appropriate?
6. **HPA**: If Horizontal Pod Autoscaler is configured, be conservative with limits
7. **Safety**: Always leave headroom for unexpected spikes

{simple_reference}

## Output Format

You MUST respond with valid JSON only, no additional text or explanation outside the JSON.

Required JSON structure:
{{
  "cpu_request": <float in cores, e.g., 0.25 for 250m>,
  "cpu_limit": <float in cores or null>,
  "memory_request": <integer in bytes>,
  "memory_limit": <integer in bytes>,
  "reasoning": "<brief explanation of your recommendations>",
  "confidence": <integer 0-100, your confidence in these recommendations>
}}

## Constraints

- CPU request: minimum 0.01 cores (10m), maximum 16 cores
- Memory request: minimum 104857600 bytes (100Mi), maximum 68719476736 bytes (64Gi)
- Recommendations should be practical and safe for production use
- If data is insufficient or unreliable, set confidence below 50

## Example

{{
  "cpu_request": 0.25,
  "cpu_limit": null,
  "memory_request": 536870912,
  "memory_limit": 536870912,
  "reasoning": "Based on p95 CPU at 0.18 cores with low variance, 0.25 cores provides safe headroom. Memory shows consistent usage around 480Mi with no OOM events, setting at 512Mi with matching limit.",
  "confidence": 85
}}
"""
    
    return prompt.strip()


def get_user_prompt(stats: dict, compact: bool = False) -> str:
    """Generate the user prompt with workload statistics.
    
    Args:
        stats: Statistics dictionary from extract_comprehensive_stats
        compact: Whether to use compact mode (reduced token usage)
        
    Returns:
        User prompt string
    """
    workload = stats["workload"]
    pods = stats["pods"]
    cpu = stats.get("cpu", {})
    memory = stats.get("memory", {})
    allocations = stats.get("allocations", {})
    hpa = stats.get("hpa")
    temporal = stats.get("temporal", {})
    
    prompt_parts = [
        f"## Workload: {workload['kind']} {workload['namespace']}/{workload['name']}",
        f"Container: {workload['container']}",
        f"",
        f"## Pod Information",
        f"- Current pods: {pods['current_count']}",
        f"- Deleted pods: {pods['deleted_count']}",
        f"- Total data points: {temporal.get('total_data_points', 'unknown')}",
    ]
    
    # CPU Statistics
    if cpu:
        prompt_parts.append("\n## CPU Usage Statistics")
        
        if compact:
            # Compact mode: only key percentiles and aggregate stats
            percentiles = cpu.get("percentiles", {})
            prompt_parts.extend([
                f"- P50: {percentiles.get('p50', 0):.4f} cores",
                f"- P95: {percentiles.get('p95', 0):.4f} cores",
                f"- P99: {percentiles.get('p99', 0):.4f} cores",
                f"- Max: {cpu.get('max', 0):.4f} cores",
                f"- Trend slope: {cpu.get('trend_slope', 0):.6f} (positive=increasing)",
                f"- Spike count (>2x mean): {cpu.get('spike_count', 0)}",
            ])
        else:
            # Full mode: all percentiles and per-pod breakdown
            percentiles = cpu.get("percentiles", {})
            prompt_parts.extend([
                "Percentiles:",
                f"- P50: {percentiles.get('p50', 0):.4f} cores",
                f"- P75: {percentiles.get('p75', 0):.4f} cores",
                f"- P90: {percentiles.get('p90', 0):.4f} cores",
                f"- P95: {percentiles.get('p95', 0):.4f} cores",
                f"- P99: {percentiles.get('p99', 0):.4f} cores",
                "",
                "Aggregate statistics:",
                f"- Max: {cpu.get('max', 0):.4f} cores",
                f"- Mean: {cpu.get('mean', 0):.4f} cores",
                f"- Std Dev: {cpu.get('std', 0):.4f} cores",
                f"- Trend slope: {cpu.get('trend_slope', 0):.6f} (positive=increasing)",
                f"- Spike count (>2x mean): {cpu.get('spike_count', 0)}",
            ])
            
            # Per-pod stats (first 3 pods only in full mode)
            per_pod = cpu.get("per_pod", {})
            if per_pod:
                prompt_parts.append("\nPer-pod CPU (sample):")
                for pod_name, pod_stats in list(per_pod.items())[:3]:
                    prompt_parts.append(
                        f"- {pod_name}: max={pod_stats['max']:.4f}, "
                        f"mean={pod_stats['mean']:.4f}, std={pod_stats['std']:.4f}"
                    )
    
    # Memory Statistics
    if memory:
        prompt_parts.append("\n## Memory Usage Statistics")
        
        if compact:
            # Compact mode: only aggregate stats
            prompt_parts.extend([
                f"- Max: {memory.get('max', 0):.0f} bytes ({memory.get('max', 0) / 1024**2:.1f} Mi)",
                f"- Mean: {memory.get('mean', 0):.0f} bytes ({memory.get('mean', 0) / 1024**2:.1f} Mi)",
                f"- OOM Kills detected: {'YES - CRITICAL!' if memory.get('oomkill_detected') else 'No'}",
            ])
            if memory.get('oomkill_detected'):
                oomkill_value = memory.get('oomkill_max_value', 0)
                prompt_parts.append(
                    f"- OOM Kill max memory: {oomkill_value:.0f} bytes ({oomkill_value / 1024**2:.1f} Mi)"
                )
        else:
            # Full mode: all stats and per-pod breakdown
            prompt_parts.extend([
                f"- Max: {memory.get('max', 0):.0f} bytes ({memory.get('max', 0) / 1024**2:.1f} Mi)",
                f"- Mean: {memory.get('mean', 0):.0f} bytes ({memory.get('mean', 0) / 1024**2:.1f} Mi)",
                f"- Std Dev: {memory.get('std', 0):.0f} bytes ({memory.get('std', 0) / 1024**2:.1f} Mi)",
                f"- OOM Kills detected: {'YES - CRITICAL!' if memory.get('oomkill_detected') else 'No'}",
            ])
            
            if memory.get('oomkill_detected'):
                oomkill_value = memory.get('oomkill_max_value', 0)
                prompt_parts.append(
                    f"- OOM Kill max memory: {oomkill_value:.0f} bytes ({oomkill_value / 1024**2:.1f} Mi)"
                )
            
            # Per-pod stats (first 3 pods only in full mode)
            per_pod = memory.get("per_pod", {})
            if per_pod:
                prompt_parts.append("\nPer-pod Memory (sample):")
                for pod_name, pod_stats in list(per_pod.items())[:3]:
                    prompt_parts.append(
                        f"- {pod_name}: max={pod_stats['max']:.0f} bytes "
                        f"({pod_stats['max'] / 1024**2:.1f} Mi)"
                    )
    
    # Current Allocations
    if allocations:
        prompt_parts.append("\n## Current Resource Allocations")
        cpu_alloc = allocations.get("cpu", {})
        mem_alloc = allocations.get("memory", {})
        
        cpu_req = cpu_alloc.get("request")
        cpu_lim = cpu_alloc.get("limit")
        mem_req = mem_alloc.get("request")
        mem_lim = mem_alloc.get("limit")
        
        prompt_parts.extend([
            f"CPU Request: {cpu_req if cpu_req else 'unset'}",
            f"CPU Limit: {cpu_lim if cpu_lim else 'unset'}",
            f"Memory Request: {mem_req if mem_req else 'unset'}",
            f"Memory Limit: {mem_lim if mem_lim else 'unset'}",
        ])
    
    # HPA Information
    if hpa:
        prompt_parts.append("\n## Horizontal Pod Autoscaler (HPA) Detected")
        prompt_parts.extend([
            f"- Min replicas: {hpa['min_replicas']}",
            f"- Max replicas: {hpa['max_replicas']}",
            f"- Current replicas: {hpa['current_replicas']}",
        ])
        if hpa['target_cpu_utilization']:
            prompt_parts.append(f"- Target CPU utilization: {hpa['target_cpu_utilization']}%")
        if hpa['target_memory_utilization']:
            prompt_parts.append(f"- Target memory utilization: {hpa['target_memory_utilization']}%")
        prompt_parts.append(
            "NOTE: With HPA, be conservative with limits to allow scaling to work properly."
        )
    
    # Warnings
    warnings = stats.get("warnings", [])
    if warnings:
        prompt_parts.append("\n## Warnings")
        for warning in warnings:
            prompt_parts.append(f"- {warning}")
    
    prompt_parts.append("\n## Your Task")
    prompt_parts.append(
        "Based on the above statistics, provide your resource recommendations in JSON format."
    )
    
    return "\n".join(prompt_parts)


def format_messages(
    provider: str, 
    stats: dict, 
    object_data: K8sObjectData,
    settings: "AiAssistedStrategySettings"
) -> Union[list, str]:
    """Format messages for the specific AI provider.
    
    Args:
        provider: AI provider name (openai, gemini, anthropic, ollama)
        stats: Statistics dictionary
        object_data: Kubernetes object data
        settings: Strategy settings
        
    Returns:
        Messages in provider-specific format (list of dicts or string)
    """
    system_prompt = get_system_prompt(
        provider, 
        include_simple_ref=not settings.ai_exclude_simple_reference
    )
    user_prompt = get_user_prompt(stats, compact=settings.ai_compact_mode)
    
    # OpenAI and Anthropic use message list format
    if provider.lower() in ["openai", "anthropic"]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    # Gemini and Ollama use concatenated string format
    else:
        return f"{system_prompt}\n\n{user_prompt}"
