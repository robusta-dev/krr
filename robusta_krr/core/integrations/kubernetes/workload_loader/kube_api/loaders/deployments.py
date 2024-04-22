from typing import Any

from .base import BaseKindLoader


class DeploymentLoader(BaseKindLoader):
    kind = "Deployment"

    def all_namespaces_request(self, label_selector: str) -> Any:
        return self.apps.list_deployment_for_all_namespaces(label_selector=label_selector, watch=False)

    def namespaced_request(self, namespace: str, label_selector: str) -> Any:
        return self.apps.list_namespaced_deployment(namespace=namespace, label_selector=label_selector, watch=False)
