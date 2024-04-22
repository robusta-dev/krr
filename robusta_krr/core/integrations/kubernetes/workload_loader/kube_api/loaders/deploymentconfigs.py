import logging
from typing import Any

from robusta_krr.utils.object_like_dict import ObjectLikeDict

from .base import BaseKindLoader

logger = logging.getLogger("krr")


class DeploymentConfigLoader(BaseKindLoader):
    kind = "DeploymentConfig"

    # NOTE: Using custom objects API returns dicts, but all other APIs return objects
    # We need to handle this difference using a small wrapper

    def all_namespaces_request(self, label_selector: str) -> Any:
        return ObjectLikeDict(
            self.custom_objects.list_cluster_custom_object(
                group="apps.openshift.io",
                version="v1",
                plural="deploymentconfigs",
                label_selector=label_selector,
                watch=False,
            )
        )

    def namespaced_request(self, namespace: str, label_selector: str) -> Any:
        return ObjectLikeDict(
            self.custom_objects.list_namespaced_custom_object(
                group="apps.openshift.io",
                version="v1",
                plural="deploymentconfigs",
                namespace=namespace,
                label_selector=label_selector,
                watch=False,
            )
        )
