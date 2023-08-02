from typing import Optional

from kubernetes.client import ApiClient
from prometrix import MetricsNotFound, ThanosMetricsNotFound

from robusta_krr.utils.service_discovery import MetricsServiceDiscovery

from .prometheus_metrics_service import PrometheusMetricsService


class ThanosMetricsDiscovery(MetricsServiceDiscovery):
    def find_metrics_url(self, *, api_client: Optional[ApiClient] = None) -> Optional[str]:
        """
        Finds the Thanos URL using selectors.
        Args:
            api_client (Optional[ApiClient]): A Kubernetes API client. Defaults to None.
        Returns:
            Optional[str]: The discovered Thanos URL, or None if not found.
        """

        return super().find_url(
            selectors=[
                "app.kubernetes.io/component=query,app.kubernetes.io/name=thanos",
                "app.kubernetes.io/name=thanos-query",
                "app=thanos-query",
                "app=thanos-querier",
            ]
        )


class ThanosMetricsService(PrometheusMetricsService):
    """
    A class for fetching metrics from Thanos.
    """

    service_discovery = ThanosMetricsDiscovery

    def check_connection(self):
        """
        Checks the connection to Prometheus.
        Raises:
            ThanosMetricsNotFound: If the connection to Thanos cannot be established.
        """
        try:
            super().check_connection()
        except MetricsNotFound as e:
            # This is to clarify which metrics service had the issue and not say its a prometheus issue
            raise ThanosMetricsNotFound(
                f"Couldn't connect to Thanos found under {self.prometheus.url}\nCaused by {e.__class__.__name__}: {e})"
            ) from e
