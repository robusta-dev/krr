"""
Tests for GCP Managed Prometheus metric loaders.

These tests verify that the GCP-specific loaders generate correct PromQL queries
with the kubernetes.io/* metric naming conventions and UTF-8 syntax.
"""

import pytest
from unittest.mock import Mock, patch

from robusta_krr.core.integrations.prometheus.metrics.gcp.cpu import (
    GcpCPULoader,
    GcpPercentileCPULoader,
    GcpCPUAmountLoader,
)
from robusta_krr.core.integrations.prometheus.metrics.gcp.memory import (
    GcpMemoryLoader,
    GcpMaxMemoryLoader,
    GcpMemoryAmountLoader,
)
from robusta_krr.core.models.objects import K8sObjectData, PodData
from robusta_krr.core.models.allocations import ResourceAllocations


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock settings for all tests to avoid Config not set errors."""
    mock_settings = Mock()
    mock_settings.prometheus_cluster_label = None
    mock_settings.prometheus_label = "cluster"
    mock_settings.prometheus_url = "http://test-prometheus:9090"
    mock_settings.prometheus_auth_header = None
    mock_settings.prometheus_ssl_enabled = False
    mock_settings.prometheus_other_options = {}
    mock_settings.prometheus_other_headers = {}
    mock_settings.openshift = False
    
    with patch('robusta_krr.core.integrations.prometheus.metrics.base.settings', mock_settings):
        with patch('robusta_krr.core.integrations.prometheus.metrics_service.prometheus_metrics_service.settings', mock_settings):
            with patch('robusta_krr.core.integrations.openshift.token.settings', mock_settings):
                with patch('robusta_krr.core.integrations.prometheus.prometheus_utils.settings', mock_settings):
                    yield mock_settings


@pytest.fixture
def mock_prometheus():
    """Create a mock Prometheus connection."""
    return Mock()


@pytest.fixture
def sample_k8s_object():
    """Create a sample K8s object for testing."""
    return K8sObjectData(
        cluster="test-cluster",
        name="test-deployment",
        container="nginx",
        namespace="default",
        kind="Deployment",
        allocations=ResourceAllocations(requests={}, limits={}),
        pods=[
            PodData(name="test-pod-123", deleted=False),
            PodData(name="test-pod-456", deleted=False),
        ]
    )


class TestGcpCPULoader:
    """Tests for GCP CPU metric loaders."""
    
    def test_cpu_loader_query_syntax(self, mock_prometheus, sample_k8s_object):
        """Test that GcpCPULoader generates correct UTF-8 syntax."""
        loader = GcpCPULoader(mock_prometheus, "GCP Managed Prometheus")
        query = loader.get_query(sample_k8s_object, "1h", "5m")
        
        # Verify UTF-8 syntax
        assert '{"__name__"="kubernetes.io/container/cpu/core_usage_time"' in query
        assert '"monitored_resource"="k8s_container"' in query
        
        # Verify GCP label names
        assert '"namespace_name"="default"' in query
        assert '"pod_name"=~"test-pod-123|test-pod-456"' in query
        assert '"container_name"="nginx"' in query
        
        # Verify label renaming
        assert 'label_replace' in query
        assert '"pod", "$1", "pod_name"' in query
        assert '"container", "$1", "container_name"' in query
        
    def test_cpu_loader_with_cluster_label(self, mock_prometheus, sample_k8s_object, mock_settings):
        """Test GcpCPULoader with cluster label."""
        # Configure mock settings with cluster label
        mock_settings.prometheus_cluster_label = "my-cluster"
        mock_settings.prometheus_label = "cluster_name"
        
        loader = GcpCPULoader(mock_prometheus, "GCP Managed Prometheus")
        query = loader.get_query(sample_k8s_object, "1h", "5m")
        
        # Verify cluster label is included
        assert '"cluster_name"="my-cluster"' in query or ', cluster_name="my-cluster"' in query
        
    def test_percentile_cpu_loader_factory(self, mock_prometheus, sample_k8s_object):
        """Test that PercentileCPULoader factory creates correct loaders."""
        # Test 95th percentile
        Loader95 = GcpPercentileCPULoader(95)
        assert hasattr(Loader95, '_percentile')
        assert Loader95._percentile == 95
        
        loader = Loader95(mock_prometheus, "GCP Managed Prometheus")
        query = loader.get_query(sample_k8s_object, "1h", "5m")
        
        assert 'quantile_over_time' in query
        assert '0.95,' in query  # 95th percentile = 0.95
        
        # Test 99th percentile
        Loader99 = GcpPercentileCPULoader(99)
        assert Loader99._percentile == 99
        
        loader = Loader99(mock_prometheus, "GCP Managed Prometheus")
        query = loader.get_query(sample_k8s_object, "1h", "5m")
        
        assert '0.99,' in query
        
    def test_percentile_cpu_loader_invalid_percentile(self):
        """Test that invalid percentiles raise ValueError."""
        with pytest.raises(ValueError):
            GcpPercentileCPULoader(150)  # > 100
            
        with pytest.raises(ValueError):
            GcpPercentileCPULoader(-5)  # < 0
    
    def test_cpu_amount_loader_query(self, mock_prometheus, sample_k8s_object):
        """Test GcpCPUAmountLoader generates count_over_time query."""
        loader = GcpCPUAmountLoader(mock_prometheus, "GCP Managed Prometheus")
        query = loader.get_query(sample_k8s_object, "24h", "5m")
        
        assert 'count_over_time' in query
        assert '[24h:5m]' in query


class TestGcpMemoryLoader:
    """Tests for GCP Memory metric loaders."""
    
    def test_memory_loader_query_syntax(self, mock_prometheus, sample_k8s_object):
        """Test that GcpMemoryLoader generates correct UTF-8 syntax."""
        loader = GcpMemoryLoader(mock_prometheus, "GCP Managed Prometheus")
        query = loader.get_query(sample_k8s_object, "1h", "5m")
        
        # Verify UTF-8 syntax
        assert '{"__name__"="kubernetes.io/container/memory/used_bytes"' in query
        assert '"monitored_resource"="k8s_container"' in query
        
        # Verify GCP label names
        assert '"namespace_name"="default"' in query
        assert '"pod_name"=~"test-pod-123|test-pod-456"' in query
        assert '"container_name"="nginx"' in query
        
        # Verify label renaming
        assert 'label_replace' in query
        
    def test_max_memory_loader_query(self, mock_prometheus, sample_k8s_object):
        """Test GcpMaxMemoryLoader generates max_over_time query."""
        loader = GcpMaxMemoryLoader(mock_prometheus, "GCP Managed Prometheus")
        query = loader.get_query(sample_k8s_object, "7d", "5m")
        
        assert 'max_over_time' in query
        assert '[7d:5m]' in query
        
    def test_memory_amount_loader_query(self, mock_prometheus, sample_k8s_object):
        """Test GcpMemoryAmountLoader generates count_over_time query."""
        loader = GcpMemoryAmountLoader(mock_prometheus, "GCP Managed Prometheus")
        query = loader.get_query(sample_k8s_object, "24h", "5m")
        
        assert 'count_over_time' in query
        assert '[24h:5m]' in query


class TestQuerySyntaxValidation:
    """Tests to validate PromQL syntax correctness."""
    
    def test_no_syntax_errors_in_queries(self, mock_prometheus, sample_k8s_object):
        """Verify generated queries don't have obvious syntax errors."""
        loaders = [
            GcpCPULoader,
            GcpCPUAmountLoader,
            GcpMemoryLoader,
            GcpMaxMemoryLoader,
            GcpMemoryAmountLoader,
        ]
        
        for LoaderClass in loaders:
            loader = LoaderClass(mock_prometheus, "GCP Managed Prometheus")
            query = loader.get_query(sample_k8s_object, "1h", "5m")
            
            # Check for common syntax errors
            assert ',,' not in query, f"Double comma in {LoaderClass.__name__} query"
            assert ',}' not in query, f"Comma before closing brace in {LoaderClass.__name__} query"
            assert query.count('{') == query.count('}'), f"Unbalanced braces in {LoaderClass.__name__} query"
            assert query.count('(') == query.count(')'), f"Unbalanced parentheses in {LoaderClass.__name__} query"


class TestGcpMetricsService:
    """Tests for GcpManagedPrometheusMetricsService."""
    
    def test_loader_mapping(self):
        """Test that all expected loaders are mapped."""
        from robusta_krr.core.integrations.prometheus.metrics_service.gcp_metrics_service import (
            GcpManagedPrometheusMetricsService
        )
        
        mapping = GcpManagedPrometheusMetricsService.LOADER_MAPPING
        
        # Verify CPU loaders are mapped
        assert "CPULoader" in mapping
        assert "PercentileCPULoader" in mapping
        assert "CPUAmountLoader" in mapping
        
        # Verify Memory loaders are mapped
        assert "MemoryLoader" in mapping
        assert "MaxMemoryLoader" in mapping
        assert "MemoryAmountLoader" in mapping
        
        # Verify unsupported loader is marked as None
        assert "MaxOOMKilledMemoryLoader" in mapping
        assert mapping["MaxOOMKilledMemoryLoader"] is None

