import logging

from cachetools import TTLCache
from kubernetes import client
from kubernetes.client import V1ServiceList
from kubernetes.client.api_client import ApiClient
from kubernetes.client.models.v1_service import V1Service

from robusta_krr.utils.configurable import Configurable


class ServiceDiscovery(Configurable):
    SERVICE_CACHE_TTL_SEC = 900
    cache: TTLCache = TTLCache(maxsize=1, ttl=SERVICE_CACHE_TTL_SEC)

    def find_service_url(self, label_selector: str, *, api_client: ApiClient | None = None) -> str | None:
        """
        Get the url of an in-cluster service with a specific label
        """
        # we do it this way because there is a weird issue with hikaru's ServiceList.listServiceForAllNamespaces()
        v1 = client.CoreV1Api(api_client=api_client)
        svc_list: V1ServiceList = v1.list_service_for_all_namespaces(label_selector=label_selector)
        if not svc_list.items:
            return None

        svc: V1Service = svc_list.items[0]
        name = svc.metadata.name
        namespace = svc.metadata.namespace
        port = svc.spec.ports[0].port

        if self.config.inside_cluster:
            return f"http://{name}.{namespace}.svc.cluster.local:{port}"

        elif api_client is not None:
            return f"{api_client.configuration.host}/api/v1/namespaces/{namespace}/services/{name}:{port}/proxy"

        return None

    def find_url(self, selectors: list[str], *, api_client: ApiClient | None = None) -> str | None:
        """
        Try to autodiscover the url of an in-cluster service
        """
        cache_key = ",".join(selectors)
        cached_value = self.cache.get(cache_key)
        if cached_value:
            return cached_value

        for label_selector in selectors:
            logging.debug(f"Trying to find service with label selector {label_selector}")
            service_url = self.find_service_url(label_selector, api_client=api_client)
            if service_url:
                logging.debug(f"Found service with label selector {label_selector}")
                self.cache[cache_key] = service_url
                return service_url

        return None
