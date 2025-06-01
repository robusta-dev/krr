import copy
import logging
from typing import Dict, Any, List, Optional
from enforcer.model import ContainerRecommendation
from enforcer.env_vars import UPDATE_THRESHOLD
logger = logging.getLogger()

REQ = "requests"
LIM = "limits"
CPU = "cpu"
MEM = "memory"


def to_cpu_num(cpu_str: Optional[str]) -> Optional[float]:
    """
    Convert Kubernetes CPU request string to float number of CPUs.

    Args:
        cpu_str: CPU string like "100m", "0.5", "1", "2.5", or None

    Returns:
        Float number of CPUs or None if input is None

    Examples:
        "100m" -> 0.1
        "1500m" -> 1.5
        "0.5" -> 0.5
        "1" -> 1.0
        "2.5" -> 2.5
        None -> None
    """
    if cpu_str is None:
        return None

    cpu_str = cpu_str.strip()
    if not cpu_str:
        return None

    # Handle millicpu format (e.g., "100m", "1500m")
    if cpu_str.endswith('m'):
        return float(cpu_str[:-1]) / 1000.0
    if cpu_str.endswith('k'):
        return float(cpu_str[:-1]) * 1000.0

    # Handle regular float/int format (e.g., "0.5", "1", "2.5")
    try:
        return float(cpu_str)
    except ValueError:
        logger.warning(f"Invalid CPU string format: {cpu_str}")
        return None


def to_mem_bytes(mem_str: Optional[str]) -> Optional[int]:
    """
    Convert Kubernetes memory request string to bytes.

    Args:
        mem_str: Memory string like "128Mi", "1Gi", "256M", "1000000000", or None

    Returns:
        Integer number of bytes or None if input is None

    Examples:
        "128Mi" -> 134217728 (128 * 1024 * 1024)
        "1Gi" -> 1073741824 (1 * 1024 * 1024 * 1024)
        "256M" -> 256000000 (256 * 1000 * 1000)
        "1000" -> 1000
        None -> None
    """
    if mem_str is None:
        return None

    mem_str = mem_str.strip()
    if not mem_str:
        return None

    # Binary (base 1024) suffixes
    binary_suffixes = {
        'Ki': 1024,
        'Mi': 1024 ** 2,
        'Gi': 1024 ** 3,
        'Ti': 1024 ** 4,
        'Pi': 1024 ** 5,
        'Ei': 1024 ** 6,
    }

    # Decimal (base 1000) suffixes
    decimal_suffixes = {
        'k': 1000,
        'M': 1000 ** 2,
        'G': 1000 ** 3,
        'T': 1000 ** 4,
        'P': 1000 ** 5,
        'E': 1000 ** 6,
    }

    # Check binary suffixes first (more common in K8s)
    for suffix, multiplier in binary_suffixes.items():
        if mem_str.endswith(suffix):
            try:
                return int(float(mem_str[:-len(suffix)]) * multiplier)
            except ValueError:
                logger.warning(f"Invalid memory string format: {mem_str}")
                return None

    # Check decimal suffixes
    for suffix, multiplier in decimal_suffixes.items():
        if mem_str.endswith(suffix):
            try:
                return int(float(mem_str[:-len(suffix)]) * multiplier)
            except ValueError:
                logger.warning(f"Invalid memory string format: {mem_str}")
                return None

    # No suffix, assume bytes
    try:
        return int(float(mem_str))
    except ValueError:
        logger.warning(f"Invalid memory string format: {mem_str}")
        return None


def significant_diff(old: Optional[float], new: float, percent_threshold: float) -> bool:
    if not old:  # old cpu is none or 0
        return True

    percent_diff = abs(new - old) / abs(old) * 100
    return percent_diff > percent_threshold


def add_resource_value(resources: Dict[str, Any], resource_type: str, resource_name: str, resource_value: Any) -> None:
    if resource_type not in resources:
        resources[resource_type] = {}
    resources[resource_type][resource_name] = str(resource_value)


def get_updated_resources(resources: Dict[str, Any], recommendation: ContainerRecommendation) -> Dict[str, Any]:
    if recommendation.cpu:
        old_cpu_req = to_cpu_num(resources.get(REQ, {}).get(CPU))
        if old_cpu_req:
            if significant_diff(old_cpu_req, recommendation.cpu.request, UPDATE_THRESHOLD):
                add_resource_value(resources, REQ, CPU, recommendation.cpu.request)
        else:
            add_resource_value(resources, REQ, CPU, recommendation.cpu.request)

        old_cpu_lim = to_cpu_num(resources.get(LIM, {}).get(CPU))
        if old_cpu_lim:
            if not recommendation.cpu.limit:  # remove limit
                del resources[LIM][CPU]
            else:
                if significant_diff(old_cpu_lim, recommendation.cpu.limit, UPDATE_THRESHOLD):
                    add_resource_value(resources, LIM, CPU, recommendation.cpu.limit)
        elif recommendation.cpu.limit:  # no old cpu limit, but recommended cpu limit (unlikely)
            add_resource_value(resources, LIM, CPU, recommendation.cpu.limit)

    if recommendation.memory:
        old_mem_req = to_mem_bytes(resources.get(REQ, {}).get(MEM))
        if old_mem_req:
            if significant_diff(old_mem_req, recommendation.memory.request, UPDATE_THRESHOLD):
                add_resource_value(resources, REQ, MEM, recommendation.memory.request)
        else:
            add_resource_value(resources, REQ, MEM, recommendation.memory.request)

        old_mem_lim = to_mem_bytes(resources.get(LIM, {}).get(MEM))
        if old_mem_lim:
            if not recommendation.memory.limit:  # remove limit
                del resources[LIM][MEM]
            else:
                if significant_diff(old_mem_lim, recommendation.memory.limit, UPDATE_THRESHOLD):
                    add_resource_value(resources, LIM, MEM, recommendation.memory.limit)
        elif recommendation.memory.limit:  # no old memory limit, but recommended memory limit
            add_resource_value(resources, LIM, MEM, recommendation.memory.limit)

    return resources

def validate_resources(resources: Dict[str, Any]) -> bool:
    """
    Validate that resource requests and limits are valid.
    
    Rules:
    1. If request is defined, it must be > 0
    2. If both request and limit are defined, limit >= request
    
    Args:
        resources: Resource dict with requests/limits (K8s format with string values)
        
    Returns:
        True if valid, False if invalid
    """
    requests = resources.get(REQ, {})
    limits = resources.get(LIM, {})
    
    # Validate CPU
    cpu_req_str = requests.get(CPU)
    cpu_lim_str = limits.get(CPU)
    
    cpu_req = to_cpu_num(cpu_req_str) if cpu_req_str else None
    cpu_lim = to_cpu_num(cpu_lim_str) if cpu_lim_str else None
    
    # Rule 1: CPU request must be > 0 if defined
    if cpu_req is not None and cpu_req <= 0:
        logger.warning(f"Invalid CPU request: {cpu_req_str} (must be > 0)")
        return False
    
    # Rule 2: CPU limit >= request if both defined
    if cpu_req is not None and cpu_lim is not None and cpu_lim < cpu_req:
        logger.warning(f"Invalid CPU: limit {cpu_lim_str} < request {cpu_req_str}")
        return False
    
    # Validate Memory
    mem_req_str = requests.get(MEM)
    mem_lim_str = limits.get(MEM)
    
    mem_req = to_mem_bytes(mem_req_str) if mem_req_str else None
    mem_lim = to_mem_bytes(mem_lim_str) if mem_lim_str else None
    
    # Rule 1: Memory request must be > 0 if defined
    if mem_req is not None and mem_req <= 0:
        logger.warning(f"Invalid memory request: {mem_req_str} (must be > 0)")
        return False
    
    # Rule 2: Memory limit >= request if both defined
    if mem_req is not None and mem_lim is not None and mem_lim < mem_req:
        logger.warning(f"Invalid memory: limit {mem_lim_str} < request {mem_req_str}")
        return False
    
    return True

def patch_container_resources(
        container_index: int,
        container: Dict[str, Any],
        recommendation: Optional[ContainerRecommendation]) -> List[Dict[str, Any]]:
    """
    Validate container resources and return patches if needed.

    Returns:
        List[Dict[str, Any]]: List of patches to apply
    """
    patches = []

    if not recommendation:
        return patches

    had_resources = "resources" in container
    resources = copy.deepcopy(container.get('resources', {}))
    updated_resources = get_updated_resources(container.get('resources', {}), recommendation)

    if resources != updated_resources:
        if validate_resources(updated_resources):
            patches.append({
                "op": "replace" if had_resources else "add",
                "path": f"/spec/containers/{container_index}/resources",
                "value": updated_resources
            })

    return patches
