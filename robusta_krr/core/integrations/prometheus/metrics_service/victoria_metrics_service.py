from typing import Optional

from kubernetes.client import ApiClient
from prometrix import MetricsNotFound, VictoriaMetricsNotFound

from robusta_krr.utils.service_discovery import MetricsServiceDiscovery

from .prometheus_metrics_service import PrometheusMetricsService


class VictoriaMetricsDiscovery(MetricsServiceDiscovery):
    def find_metrics_url(self, *, api_client: Optional[ApiClient] = None) -> Optional[str]:
        """
        Finds the Victoria Metrics URL using selectors.
        Args:
            api_client (Optional[ApiClient]): A Kubernetes API client. Defaults to None.
        Returns:
            Optional[str]: The discovered Victoria Metrics URL, or None if not found.
        """
        url = super().find_url(
            selectors=[
                "app.kubernetes.io/name=vmsingle",
                "app.kubernetes.io/name=victoria-metrics-single",
            ]
        )
        if url is None:
            url = super().find_url(
                selectors=[
                    "app.kubernetes.io/name=vmselect",
                    "app=vmselect",
                ]
            )
            if url is not None:
                url = f"{url}/select/0/prometheus/"
        return url


class VictoriaMetricsService(PrometheusMetricsService):
    """
    A class for fetching metrics from Victoria Metrics.
    """

    service_discovery = VictoriaMetricsDiscovery

    @classmethod
    def name(cls) -> str:
        return "Victoria Metrics"

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
