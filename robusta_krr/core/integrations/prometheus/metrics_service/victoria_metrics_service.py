from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from kubernetes.client import ApiClient
from requests.exceptions import ConnectionError, HTTPError

from robusta_krr.core.models.config import Config
from robusta_krr.utils.service_discovery import ServiceDiscovery

from .prometheus_metrics_service import MetricsNotFound, PrometheusMetricsService


class VictoriaMetricsDiscovery(ServiceDiscovery):
    def find_metrics_url(self, *, api_client: Optional[ApiClient] = None) -> Optional[str]:
        """
        Finds the Victoria Metrics URL using selectors.
        Args:
            api_client (Optional[ApiClient]): A Kubernetes API client. Defaults to None.
        Returns:
            Optional[str]: The discovered Victoria Metrics URL, or None if not found.
        """
        return super().find_url(
            selectors=[
                "app.kubernetes.io/name=vmsingle",
                "app.kubernetes.io/name=victoria-metrics-single",
                "app.kubernetes.io/name=vmselect",
                "app=vmselect",
            ]
        )


class VictoriaMetricsNotFound(MetricsNotFound):
    """
    An exception raised when Victoria Metrics is not found.
    """

    pass


class VictoriaMetricsService(PrometheusMetricsService):
    """
    A class for fetching metrics from Victoria Metrics.
    """

    def __init__(
        self,
        config: Config,
        *,
        cluster: Optional[str] = None,
        api_client: Optional[ApiClient] = None,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        super().__init__(
            config=config,
            cluster=cluster,
            api_client=api_client,
            service_discovery=VictoriaMetricsDiscovery,
            executor=executor,
        )

    def check_connection(self):
        """
        Checks the connection to Prometheus.
        Raises:
            VictoriaMetricsNotFound: If the connection to Victoria Metrics cannot be established.
        """
        try:
            super().check_connection()
        except MetricsNotFound as e:
            # This is to clarify which metrics service had the issue and not say its a prometheus issue
            raise VictoriaMetricsNotFound(
                f"Couldn't connect to Victoria Metrics found under {self.prometheus.url}\nCaused by {e.__class__.__name__}: {e})"
            ) from e
