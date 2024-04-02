from typing import Optional

from kubernetes.client import ApiClient
from prometrix import MetricsNotFound

from robusta_krr.utils.service_discovery import MetricsServiceDiscovery

from .prometheus_metrics_service import PrometheusMetricsService

class MimirMetricsDiscovery(MetricsServiceDiscovery):
    def find_metrics_url(self, *, api_client: Optional[ApiClient] = None) -> Optional[str]:
        """
        Finds the Mimir Metrics URL using selectors.
        Args:
            api_client (Optional[ApiClient]): A Kubernetes API client. Defaults to None.
        Returns:
            Optional[str]: The discovered Mimir Metrics URL, or None if not found.
        """
        return super().find_url(
            selectors=[
                "app.kubernetes.io/name=mimir,app.kubernetes.io/component=query-frontend",
            ]
        )


class MimirMetricsService(PrometheusMetricsService):
    """
    A class for fetching metrics from Mimir Metrics.
    """

    service_discovery = MimirMetricsDiscovery
    url_postfix = "/prometheus"
    additional_headers = {"X-Scope-OrgID": "anonymous"}

    def check_connection(self):
        """
        Checks the connection to Prometheus.
        Raises:
            MimirMetricsNotFound: If the connection to Mimir Metrics cannot be established.
        """
        try:
            super().check_connection()
        except MetricsNotFound as e:
            # This is to clarify which metrics service had the issue and not say its a prometheus issue
            raise MetricsNotFound(
                f"Couldn't connect to Mimir Metrics found under {self.prometheus.url}\nCaused by {e.__class__.__name__}: {e})"
            ) from e
