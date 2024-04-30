from typing import Any

from .base import BaseKindLoader


class StatefulSetLoader(BaseKindLoader):
    kind = "StatefulSet"

    def all_namespaces_request(self, label_selector: str) -> Any:
        return self.apps.list_stateful_set_for_all_namespaces(label_selector=label_selector, watch=False)

    def namespaced_request(self, namespace: str, label_selector: str) -> Any:
        return self.apps.list_namespaced_stateful_set(namespace=namespace, label_selector=label_selector, watch=False)
