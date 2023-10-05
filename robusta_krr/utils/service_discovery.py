import logging
from abc import ABC, abstractmethod
from typing import Optional

from cachetools import TTLCache
from kubernetes import client
from kubernetes.client import V1IngressList, V1ServiceList
from kubernetes.client.api_client import ApiClient
from kubernetes.client.models.v1_ingress import V1Ingress
from kubernetes.client.models.v1_service import V1Service

from robusta_krr.core.models.config import settings

logger = logging.getLogger("krr")


class ServiceDiscovery:
    SERVICE_CACHE_TTL_SEC = 900
    cache: TTLCache = TTLCache(maxsize=1, ttl=SERVICE_CACHE_TTL_SEC)

    def __init__(self, api_client: Optional[ApiClient] = None) -> None:
        self.api_client = api_client

    def find_service_url(self, label_selector: str) -> Optional[str]:
        """
        Get the url of an in-cluster service with a specific label
        """
        # we do it this way because there is a weird issue with hikaru's ServiceList.listServiceForAllNamespaces()
        v1 = client.CoreV1Api(api_client=self.api_client)
        svc_list: V1ServiceList = v1.list_service_for_all_namespaces(label_selector=label_selector)
        if not svc_list.items:
            return None

        svc: V1Service = svc_list.items[0]
        name = svc.metadata.name
        namespace = svc.metadata.namespace
        port = svc.spec.ports[0].port

        if settings.inside_cluster:
            return f"http://{name}.{namespace}.svc.cluster.local:{port}"

        elif self.api_client is not None:
            return f"{self.api_client.configuration.host}/api/v1/namespaces/{namespace}/services/{name}:{port}/proxy"

        return None

    def find_ingress_host(self, label_selector: str) -> Optional[str]:
        """
        Discover the ingress host of the Prometheus if krr is not running in cluster
        """
        if settings.inside_cluster:
            return None

        v1 = client.NetworkingV1Api(api_client=self.api_client)
        ingress_list: V1IngressList = v1.list_ingress_for_all_namespaces(label_selector=label_selector)
        if not ingress_list.items:
            return None

        ingress: V1Ingress = ingress_list.items[0]
        prometheus_host = ingress.spec.rules[0].host
        return f"http://{prometheus_host}"

    def find_url(self, selectors: list[str]) -> Optional[str]:
        """
        Try to autodiscover the url of an in-cluster service
        """
        cache_key = ",".join(selectors + [self.api_client.configuration.host if self.api_client else ""])
        cached_value = self.cache.get(cache_key)
        if cached_value:
            return cached_value

        for label_selector in selectors:
            logger.debug(f"Trying to find service with label selector {label_selector}")
            service_url = self.find_service_url(label_selector)
            if service_url:
                logger.debug(f"Found service with label selector {label_selector}")
                self.cache[cache_key] = service_url
                return service_url

            logger.debug(f"Trying to find ingress with label selector {label_selector}")
            self.find_ingress_host(label_selector)
            ingress_url = self.find_ingress_host(label_selector)
            if ingress_url:
                return ingress_url

        return None


class MetricsServiceDiscovery(ServiceDiscovery, ABC):
    @abstractmethod
    def find_metrics_url(self, *, api_client: Optional[ApiClient] = None) -> Optional[str]:
        pass
