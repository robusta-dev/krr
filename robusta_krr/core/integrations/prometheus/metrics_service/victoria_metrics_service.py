from typing import Optional
from kubernetes.client import ApiClient
from requests.exceptions import ConnectionError, HTTPError

from robusta_krr.core.models.config import Config
from robusta_krr.utils.service_discovery import ServiceDiscovery

from .prometheus_metrics_service import PrometheusMetricsService, PrometheusNotFound

class VictoriaMetricsDiscovery(ServiceDiscovery):
    def find_prometheus_url(self, *, api_client: Optional[ApiClient] = None) -> Optional[str]:
        return super().find_url(
            selectors=[
                "app.kubernetes.io/name=vmsingle",
                "app.kubernetes.io/name=victoria-metrics-single",
                "app.kubernetes.io/name=vmselect"
                "app=vmselect",

            ],
            api_client=api_client,
        )

class VictoriaMetricsNotFound(Exception):
    pass

class VictoriaMetricsService(PrometheusMetricsService):
    def __init__(
        self,
        config: Config,
        *,
        cluster: Optional[str] = None,
        api_client: Optional[ApiClient] = None,
    ) -> None:
        super().__init__(config=config, cluster=cluster, api_client=api_client, service_discovery=VictoriaMetricsDiscovery)

    def check_connection(self):
        try:
            super().check_connection()
        except PrometheusNotFound as e:
            # This is to clarify which metrics service had the issue and not say its a prometheus issue
            raise VictoriaMetricsNotFound(
                f"Couldn't connect to Victoria Metrics found under {self.prometheus.url}\nCaused by {e.__class__.__name__}: {e})"
            ) from e
