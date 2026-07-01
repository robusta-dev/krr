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
    assert loader.custom_objects.list_cluster_custom_object.call_count == 2
