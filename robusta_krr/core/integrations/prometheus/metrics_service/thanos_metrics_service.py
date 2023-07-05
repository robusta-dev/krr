from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from kubernetes.client import ApiClient

from robusta_krr.core.models.config import Config
from robusta_krr.utils.service_discovery import MetricsServiceDiscovery

from .prometheus_metrics_service import MetricsNotFound, PrometheusMetricsService


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


class ThanosMetricsNotFound(MetricsNotFound):
    """
    An exception raised when Thanos is not found.
    """

    pass


class ThanosMetricsService(PrometheusMetricsService):
    """
    A class for fetching metrics from Thanos.
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
            service_discovery=ThanosMetricsDiscovery,
            executor=executor,
        )

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
