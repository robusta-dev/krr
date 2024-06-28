import abc
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterable, Optional, Union

from kubernetes import client  # type: ignore
from kubernetes.client.api_client import ApiClient  # type: ignore
from kubernetes.client.models import V1Container, V1PodList  # type: ignore

from robusta_krr.core.models.objects import K8sWorkload, KindLiteral, PodData

logger = logging.getLogger("krr")

HPAKey = tuple[str, str, str]


class BaseKindLoader(abc.ABC):
    """
    This class is used to define how to load a specific kind of Kubernetes object.
    It does not load the objects itself, but is used by the `KubeAPIWorkloadLoader` to load objects.
    """

    kind: KindLiteral

    def __init__(self, api_client: Optional[ApiClient], executor: ThreadPoolExecutor) -> None:
        self.executor = executor
        self.api_client = api_client
        self.apps = client.AppsV1Api(api_client=self.api_client)
        self.custom_objects = client.CustomObjectsApi(api_client=self.api_client)
        self.batch = client.BatchV1Api(api_client=self.api_client)
        self.core = client.CoreV1Api(api_client=self.api_client)

    @abc.abstractmethod
    def all_namespaces_request(self, label_selector: str) -> Any:
        pass

    async def all_namespaces_request_async(self, label_selector: str) -> Any:
        """Default async implementation executes the request in a thread pool."""

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: self.all_namespaces_request(
                label_selector=label_selector,
            ),
        )

    @abc.abstractmethod
    def namespaced_request(self, namespace: str, label_selector: str) -> Any:
        pass

    async def namespaced_request_async(self, namespace: str, label_selector: str) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor,
            lambda: self.namespaced_request(
                namespace=namespace,
                label_selector=label_selector,
            ),
        )

    async def extract_containers(self, item: Any) -> Iterable[V1Container]:
        return item.spec.template.spec.containers

    def filter(self, item: Any) -> bool:
        return True

    async def list_pods(self, object: K8sWorkload) -> list[PodData]:
        loop = asyncio.get_running_loop()

        if object.selector is None:
            return []

        selector = self._build_selector_query(object.selector)
        if selector is None:
            return []

        ret: V1PodList = await loop.run_in_executor(
            self.executor,
            lambda: self.core.list_namespaced_pod(
                namespace=object._api_resource.metadata.namespace, label_selector=selector
            ),
        )

        return [PodData(name=pod.metadata.name, deleted=False) for pod in ret.items]

    @classmethod
    def _get_match_expression_filter(cls, expression: Any) -> str:
        if expression.operator.lower() == "exists":
            return expression.key
        elif expression.operator.lower() == "doesnotexist":
            return f"!{expression.key}"

        values = ",".join(expression.values)
        return f"{expression.key} {expression.operator} ({values})"

    @classmethod
    def _build_selector_query(cls, selector: Any) -> Union[str, None]:
        label_filters = []

        if selector.match_labels is not None:
            label_filters += [f"{label[0]}={label[1]}" for label in selector.match_labels.items()]

        # normally the kubernetes API client renames matchLabels to match_labels in python
        # but for CRDs like ArgoRollouts that renaming doesn't happen
        if getattr(selector, "matchLabels", None):
            label_filters += [f"{label[0]}={label[1]}" for label in getattr(selector, "matchLabels").items()]

        if selector.match_expressions is not None:
            label_filters += [cls._get_match_expression_filter(expression) for expression in selector.match_expressions]

        if label_filters == []:
            # NOTE: This might mean that we have DeploymentConfig,
            # which uses ReplicationController and it has a dict like matchLabels
            if len(selector) != 0:
                label_filters += [f"{label[0]}={label[1]}" for label in selector.items()]
            else:
                return None

        return ",".join(label_filters)
