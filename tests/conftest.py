import random
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from robusta_krr.api.models import K8sWorkload, PodData, ResourceAllocations
from robusta_krr.strategies.simple import SimpleStrategy, SimpleStrategySettings
from robusta_krr.core.integrations.prometheus.connector import PrometheusConnector
from robusta_krr.core.integrations.prometheus.metrics_service.prometheus_metrics_service import PrometheusMetricsService
from robusta_krr.core.models.config import Config
from robusta_krr.core.integrations.kubernetes.cluster_loader import KubeAPIClusterLoader, KubeAPIWorkloadLoader


TEST_OBJECT = K8sWorkload(
    cluster="mock-cluster",
    name="mock-object-1",
    container="mock-container-1",
    pods=[
        PodData(name="mock-pod-1", deleted=False),
        PodData(name="mock-pod-2", deleted=False),
        PodData(name="mock-pod-3", deleted=True),
    ],
    namespace="default",
    kind="Deployment",
    allocations=ResourceAllocations(
        requests={"cpu": 1, "memory": 1},  # type: ignore
        limits={"cpu": 2, "memory": 2},  # type: ignore
    ),
)


@pytest.fixture(autouse=True, scope="session")
def mock_list_clusters():
    with patch.object(
        KubeAPIClusterLoader,
        "list_clusters",
        new=AsyncMock(return_value=[TEST_OBJECT.cluster]),
    ):
        yield


@pytest.fixture(autouse=True, scope="session")
def mock_list_scannable_objects():
    with patch.object(
        KubeAPIWorkloadLoader,
        "list_workloads",
        new=AsyncMock(return_value=[TEST_OBJECT]),
    ):
        yield


@pytest.fixture(autouse=True, scope="session")
def mock_load_kubeconfig():
    with patch.object(Config, "load_kubeconfig", return_value=None):
        with patch.object(Config, "get_kube_client", return_value=None):
            yield


@pytest.fixture(autouse=True, scope="session")
def mock_prometheus_loader():
    now = datetime.now()
    start = now - timedelta(hours=1)
    now_ts, start_ts = now.timestamp(), start.timestamp()
    metric_points_data = np.array([(t, random.randrange(0, 100)) for t in np.linspace(start_ts, now_ts, 3600)])

    settings = SimpleStrategySettings()
    strategy = SimpleStrategy(settings)

    with patch.object(
        PrometheusConnector,
        "gather_data",
        new=AsyncMock(
            return_value={
                metric.__name__: {pod.name: metric_points_data for pod in TEST_OBJECT.pods}
                for metric in strategy.metrics
            },
        ),
    ) as mock_prometheus_loader:
        mock_prometheus_loader
        yield


@pytest.fixture(autouse=True, scope="session")
def mock_prometheus_load_pods():
    with patch.object(
        PrometheusConnector,
        "load_pods",
        new=AsyncMock(
            return_value=TEST_OBJECT.pods,
        ),
    ) as mock_prometheus_loader:
        mock_prometheus_loader
        yield


@pytest.fixture(autouse=True, scope="session")
def mock_prometheus_get_history_range():
    async def get_history_range(self, history_duration: timedelta) -> tuple[datetime, datetime]:
        now = datetime.now()
        start = now - history_duration
        return start, now

    with patch.object(PrometheusConnector, "get_history_range", get_history_range):
        yield


@pytest.fixture(autouse=True, scope="session")
def mock_prometheus_connector_connect():
    def _connect(self, loader) -> None:
        self.loader = loader

    with patch.object(PrometheusConnector, "_connect", _connect):
        with patch.object(PrometheusMetricsService, "discover", return_value=None):
            yield
