from unittest.mock import MagicMock, patch

import pytest
from kubernetes.client import ApiException

from robusta_krr.core.integrations.kubernetes import ClusterLoader
from robusta_krr.core.models.config import Config


@pytest.fixture
def mock_config():
    config = MagicMock(spec=Config)
    config.max_workers = 4
    config.get_kube_client = MagicMock()
    config.resources = "*"
    config.selector = None
    config.namespaces = "*"
    return config


@pytest.fixture
def loader(mock_config):
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        yield ClusterLoader(cluster="test-cluster")


@pytest.fixture
def namespaced_loader(mock_config):
    mock_config.namespaces = ["sentry"]
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        yield ClusterLoader(cluster="test-cluster")


def test_resolve_strimzipodset_api_version_prefers_v1(loader):
    loader.custom_objects = MagicMock()

    version = loader._resolve_strimzipodset_api_version()

    assert version == "v1"
    loader.custom_objects.list_cluster_custom_object.assert_called_once_with(
        group="core.strimzi.io",
        version="v1",
        plural="strimzipodsets",
        limit=1,
    )
    loader.custom_objects.list_namespaced_custom_object.assert_not_called()


def test_resolve_strimzipodset_api_version_falls_back_to_v1beta2(loader):
    loader.custom_objects = MagicMock()
    loader.custom_objects.list_cluster_custom_object.side_effect = [
        ApiException(status=404, reason="Not Found"),
        {"items": []},
    ]

    version = loader._resolve_strimzipodset_api_version()

    assert version == "v1beta2"
    assert loader.custom_objects.list_cluster_custom_object.call_count == 2
    loader.custom_objects.list_cluster_custom_object.assert_any_call(
        group="core.strimzi.io",
        version="v1",
        plural="strimzipodsets",
        limit=1,
    )
    loader.custom_objects.list_cluster_custom_object.assert_any_call(
        group="core.strimzi.io",
        version="v1beta2",
        plural="strimzipodsets",
        limit=1,
    )


def test_resolve_strimzipodset_api_version_returns_none_when_unavailable(loader):
    loader.custom_objects = MagicMock()
    loader.custom_objects.list_cluster_custom_object.side_effect = ApiException(status=404, reason="Not Found")

    version = loader._resolve_strimzipodset_api_version()

    assert version is None
    assert loader._strimzipodset_api_version_checked
    assert loader.custom_objects.list_cluster_custom_object.call_count == 2


def test_resolve_strimzipodset_api_version_is_cached(loader):
    loader.custom_objects = MagicMock()

    assert loader._resolve_strimzipodset_api_version() == "v1"
    assert loader._resolve_strimzipodset_api_version() == "v1"
    loader.custom_objects.list_cluster_custom_object.assert_called_once()


def test_resolve_strimzipodset_api_version_uses_namespaced_probe(namespaced_loader):
    namespaced_loader.custom_objects = MagicMock()

    version = namespaced_loader._resolve_strimzipodset_api_version()

    assert version == "v1"
    namespaced_loader.custom_objects.list_cluster_custom_object.assert_not_called()
    namespaced_loader.custom_objects.list_namespaced_custom_object.assert_called_once_with(
        group="core.strimzi.io",
        version="v1",
        plural="strimzipodsets",
        namespace="sentry",
        limit=1,
    )


def test_resolve_strimzipodset_api_version_tries_v1beta2_after_v1_non_404(loader):
    loader.custom_objects = MagicMock()
    loader.custom_objects.list_cluster_custom_object.side_effect = [
        ApiException(status=403, reason="Forbidden"),
        {"items": []},
    ]

    version = loader._resolve_strimzipodset_api_version()

    assert version == "v1beta2"
    assert loader.custom_objects.list_cluster_custom_object.call_count == 2


def test_resolve_strimzipodset_api_version_does_not_cache_transient_errors(loader):
    loader.custom_objects = MagicMock()
    loader.custom_objects.list_cluster_custom_object.side_effect = RuntimeError("connection reset")

    assert loader._resolve_strimzipodset_api_version() is None
    assert not loader._strimzipodset_api_version_checked

    loader.custom_objects.list_cluster_custom_object.side_effect = None
    loader.custom_objects.list_cluster_custom_object.return_value = {"items": []}

    assert loader._resolve_strimzipodset_api_version() == "v1"
    assert loader._strimzipodset_api_version_checked


def test_resolve_strimzipodset_api_version_probes_until_namespace_succeeds(mock_config):
    mock_config.namespaces = ["blocked", "sentry"]
    with patch("robusta_krr.core.integrations.kubernetes.settings", mock_config):
        loader = ClusterLoader(cluster="test-cluster")
        loader.custom_objects = MagicMock()
        loader.custom_objects.list_namespaced_custom_object.side_effect = [
            ApiException(status=403, reason="Forbidden"),
            {"items": []},
        ]

        version = loader._resolve_strimzipodset_api_version()

        assert version == "v1"
        assert loader.custom_objects.list_namespaced_custom_object.call_count == 2
