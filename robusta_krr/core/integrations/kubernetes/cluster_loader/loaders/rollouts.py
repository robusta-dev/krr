import asyncio
import logging
from typing import Any, Iterable

from kubernetes.client.models import V1Container  # type: ignore

from robusta_krr.utils.object_like_dict import ObjectLikeDict

from .base import BaseKindLoader

logger = logging.getLogger("krr")


class RolloutLoader(BaseKindLoader):
    kind = "Rollout"

    # NOTE: Using custom objects API returns dicts, but all other APIs return objects
    # We need to handle this difference using a small wrapper

    def all_namespaces_request(self, label_selector: str) -> Any:
        return ObjectLikeDict(
            self.custom_objects.list_cluster_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                plural="rollouts",
                label_selector=label_selector,
                watch=False,
            )
        )

    def namespaced_request(self, namespace: str, label_selector: str) -> Any:
        return ObjectLikeDict(
            self.custom_objects.list_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                plural="rollouts",
                namespace=namespace,
                label_selector=label_selector,
                watch=False,
            )
        )

    async def extract_containers(self, item: Any) -> Iterable[V1Container]:
        if item.spec.template is not None:
            return item.spec.template.spec.containers

        logging.debug(
            f"Rollout has workloadRef, fetching template for {item.metadata.name} in {item.metadata.namespace}"
        )

        # Template can be None and object might have workloadRef
        workloadRef = item.spec.workloadRef
        if workloadRef is not None:
            loop = asyncio.get_running_loop()
            ret = await loop.run_in_executor(
                self.executor,
                lambda: self.apps.read_namespaced_deployment(namespace=item.metadata.namespace, name=workloadRef.name),
            )
            return ret.spec.template.spec.containers

        return []
