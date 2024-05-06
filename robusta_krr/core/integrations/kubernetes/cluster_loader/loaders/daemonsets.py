from typing import Any

from .base import BaseKindLoader


class DaemonSetLoader(BaseKindLoader):
    kind = "DaemonSet"

    def all_namespaces_request(self, label_selector: str) -> Any:
        return self.apps.list_daemon_set_for_all_namespaces(label_selector=label_selector, watch=False)

    def namespaced_request(self, namespace: str, label_selector: str) -> Any:
        return self.apps.list_namespaced_daemon_set(namespace=namespace, label_selector=label_selector, watch=False)
