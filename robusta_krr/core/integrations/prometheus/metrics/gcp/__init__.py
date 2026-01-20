"""
GCP Managed Prometheus metric loaders.

This package contains metric loaders specifically designed for Google Cloud Platform's
Managed Prometheus service, which uses different metric naming conventions than
standard Prometheus (e.g., kubernetes.io/container/cpu/core_usage_time instead of
container_cpu_usage_seconds_total).
"""

from .cpu import GcpCPUAmountLoader, GcpCPULoader, GcpPercentileCPULoader
from .memory import GcpMaxMemoryLoader, GcpMemoryAmountLoader, GcpMemoryLoader, GcpMaxOOMKilledMemoryLoader

__all__ = [
    "GcpCPULoader",
    "GcpPercentileCPULoader",
    "GcpCPUAmountLoader",
    "GcpMemoryLoader",
    "GcpMaxMemoryLoader",
    "GcpMemoryAmountLoader",
    "GcpMaxOOMKilledMemoryLoader",
]
