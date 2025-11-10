import logging

from kubernetes.client.models.v1_pod_failure_policy_rule import V1PodFailurePolicyRule

def create_monkey_patches():
    """
        The python kubernetes client will throw exceptions for specific fields that were not allowed to be None on older versions of kubernetes.
    """
    logger = logging.getLogger("krr")
    logger.debug("Creating kubernetes python cli monkey patches")

    def patched_setter_pod_failure_policy(self, on_pod_conditions):
        self._on_pod_conditions = on_pod_conditions

    V1PodFailurePolicyRule.on_pod_conditions = V1PodFailurePolicyRule.on_pod_conditions.setter(patched_setter_pod_failure_policy)
