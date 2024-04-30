from __future__ import annotations

import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Optional

from kubernetes.client.api_client import ApiClient
from kubernetes.client.exceptions import ApiException
from prometrix import MetricsNotFound, PrometheusNotFound

from robusta_krr.core.models.config import settings
from robusta_krr.core.models.objects import K8sWorkload, PodData

from .metrics_service.prometheus_metrics_service import PrometheusMetricsService
from .metrics_service.thanos_metrics_service import ThanosMetricsService
from .metrics_service.victoria_metrics_service import VictoriaMetricsService
from .metrics_service.mimir_metrics_service import MimirMetricsService

if TYPE_CHECKING:
    from robusta_krr.core.abstract.strategies import BaseStrategy, MetricsPodData

logger = logging.getLogger("krr")


class PrometheusConnector:
    def __init__(self, *, cluster: Optional[str] = None) -> None:
        """
        Initializes the Prometheus Loader.

        Args:
            cluster (Optional[str]): The name of the cluster. Defaults to None.
        """

        self.executor = ThreadPoolExecutor(settings.max_workers)
        self.cluster = cluster

    def discover(self, api_client: ApiClient) -> None:
        """Try to automatically discover a Prometheus service."""
        metrics_to_check: list[PrometheusMetricsService] = [
            VictoriaMetricsService,
            ThanosMetricsService,
            MimirMetricsService,
            PrometheusMetricsService,
        ]

        for metric_service_class in metrics_to_check:
            logger.info(f"Trying to find {metric_service_class.name()}{self._for_cluster_postfix}")
            try:
                loader = metric_service_class.discover(api_client=api_client)
                self._connect(loader)
            except Exception:
                logger.info(f"Wasn't able to find {metric_service_class.name()}{self._for_cluster_postfix}")
            else:
                return

        raise PrometheusNotFound

    def connect(self, url: Optional[str] = None) -> None:
        """Connect to a Prometheus service using a URL."""
        try:
            loader = PrometheusMetricsService(url=url)
            self._connect(loader)
        except Exception as e:
            logger.warning(f"Unable to connect to Prometheus using the provided URL ({e})")
            raise e
        else:
            logger.info(f"{loader.name()} connected successfully")

    def _connect(self, loader: PrometheusMetricsService) -> None:
        service_name = loader.name()
        try:
            loader.check_connection()
        except MetricsNotFound as e:
            logger.info(f"{service_name} not found: {e}")
            raise PrometheusNotFound(f"Wasn't able to connect to {service_name}" + self._for_cluster_postfix)
        except ApiException as e:
            logger.warning(
                f"Unable to automatically discover a {service_name}{self._for_cluster_postfix} ({e}). "
                "Try specifying how to connect to Prometheus via cli options"
            )
            raise e
        else:
            logger.info(f"{service_name} found")
            loader.validate_cluster_name()
            self.loader = loader

    async def get_history_range(
        self, history_duration: datetime.timedelta
    ) -> Optional[tuple[datetime.datetime, datetime.datetime]]:
        return await self.loader.get_history_range(history_duration)

    async def load_pods(self, object: K8sWorkload, period: datetime.timedelta) -> list[PodData]:
        try:
            return await self.loader.load_pods(object, period)
        except Exception as e:
            logger.exception(f"Failed to load pods for {object}: {e}")
            return []

    async def gather_data(
        self,
        object: K8sWorkload,
        strategy: BaseStrategy,
        period: datetime.timedelta,
        *,
        step: datetime.timedelta = datetime.timedelta(minutes=30),
    ) -> MetricsPodData:
        """
        Gathers data from Prometheus for a specified object and resource.

        Args:
            object (K8sObjectData): The Kubernetes object.
            resource (ResourceType): The resource type.
            period (datetime.timedelta): The time period for which to gather data.
            step (datetime.timedelta, optional): The time step between data points. Defaults to 30 minutes.

        Returns:
            ResourceHistoryData: The gathered resource history data.
        """

        return {
            MetricLoader.__name__: await self.loader.gather_data(object, MetricLoader, period, step)
            for MetricLoader in strategy.metrics
        }

    @property
    def _for_cluster_postfix(self) -> str:
        """The string postfix to be used in logging messages."""
        return f" for {self.cluster} cluster" if self.cluster else ""
