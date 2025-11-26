"""
Anthos-specific metric loaders for GCP Managed Prometheus.

Anthos uses slightly different metric naming compared to GKE:
- kubernetes.io/anthos/container/* instead of kubernetes.io/container/*
- Same monitored_resource="k8s_container" label
- Memory uses max_over_time instead of max_over_time
"""

from .cpu import (
    AnthosCPULoader,
    AnthosPercentileCPULoader,  # This is a factory function, not a class
    AnthosCPUAmountLoader,
)
from .memory import (
    AnthosMemoryLoader,
    AnthosMaxMemoryLoader,
    AnthosMemoryAmountLoader,
)

__all__ = [
    "AnthosCPULoader",
    "AnthosPercentileCPULoader",
    "AnthosCPUAmountLoader",
    "AnthosMemoryLoader",
    "AnthosMaxMemoryLoader",
    "AnthosMemoryAmountLoader",
]
