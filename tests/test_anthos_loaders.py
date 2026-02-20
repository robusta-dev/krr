"""
Tests for GCP Anthos metric loaders.

These tests verify that the Anthos-specific loaders generate correct PromQL queries
with the kubernetes.io/anthos/* metric naming and monitored_resource label.
"""

import pytest
from unittest.mock import Mock, patch

from robusta_krr.core.integrations.prometheus.metrics.gcp.anthos.cpu import (
    AnthosCPULoader,
    AnthosPercentileCPULoader,
    AnthosCPUAmountLoader,
)
from robusta_krr.core.integrations.prometheus.metrics.gcp.anthos.memory import (
    AnthosMemoryLoader,
    AnthosMaxMemoryLoader,
    AnthosMemoryAmountLoader,
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
    mock_settings.gcp_anthos = True
    
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
def sample_object():
    """Create a sample K8s object for testing."""
    return K8sObjectData(
        cluster="test-cluster",
        namespace="test-namespace",
        name="test-deployment",
        kind="Deployment",
        container="test-container",
        allocations=ResourceAllocations(requests={}, limits={}),
        pods=[
            PodData(name="test-pod-123", deleted=False),
            PodData(name="test-pod-456", deleted=False),
        ]
    )


class TestAnthosCPULoader:
    """Tests for Anthos CPU metric loaders."""
    
    def test_cpu_loader_uses_anthos_metric(self, mock_prometheus, sample_object):
        """Test that AnthosCPULoader uses kubernetes.io/anthos/* metric."""
        loader = AnthosCPULoader(mock_prometheus, "Anthos Metrics")
        query = loader.get_query(sample_object, "2h", "1m")
        
        # Verify Anthos metric name is used
        assert 'kubernetes.io/anthos/container/cpu/core_usage_time' in query
        assert 'kubernetes.io/container/cpu/core_usage_time' not in query
        
        # Verify monitored_resource label is present (remove whitespace for comparison)
        query_normalized = " ".join(query.split())
        assert '"monitored_resource"="k8s_container"' in query_normalized
    
    def test_cpu_loader_with_cluster_label(self, mock_prometheus, sample_object):
        """Test CPU loader query with cluster label."""
        with patch('robusta_krr.core.integrations.prometheus.metrics.base.settings') as mock_settings:
            mock_settings.prometheus_cluster_label = 'cluster_name="test-cluster"'
            mock_settings.prometheus_label = "cluster"
            
            loader = AnthosCPULoader(mock_prometheus, "Anthos Metrics")
            query = loader.get_query(sample_object, "2h", "1m")
            
            # Should have both monitored_resource and cluster_name labels
            assert "monitored_resource" in query and "k8s_container" in query
            assert 'cluster_name="test-cluster"' in query
    
    def test_percentile_cpu_loader_factory(self, mock_prometheus, sample_object):
        """Test AnthosPercentileCPULoader factory with percentile."""
        LoaderClass = AnthosPercentileCPULoader(95)
        loader = LoaderClass(mock_prometheus, "Anthos Metrics")
        query = loader.get_query(sample_object, "2h", "1m")
        
        # Verify it uses Anthos metrics
        assert 'kubernetes.io/anthos/container/cpu/core_usage_time' in query
        assert "monitored_resource" in query and "k8s_container" in query
        
        # Verify quantile wrapping
        assert 'quantile_over_time' in query
        assert '0.95' in query
    
    def test_percentile_cpu_loader_invalid_percentile(self):
        """Test that invalid percentile raises ValueError."""
        with pytest.raises(ValueError, match="Percentile must be between 0 and 100"):
            AnthosPercentileCPULoader(150)
    
    def test_cpu_amount_loader_query(self, mock_prometheus, sample_object):
        """Test AnthosCPUAmountLoader generates correct query."""
        loader = AnthosCPUAmountLoader(mock_prometheus, "Anthos Metrics")
        query = loader.get_query(sample_object, "2h", "1m")
        
        # Verify Anthos metric is used
        assert 'kubernetes.io/anthos/container/cpu/core_usage_time' in query
        assert "monitored_resource" in query and "k8s_container" in query
        
        # Verify it's counting containers
        assert 'count' in query.lower()


class TestAnthosMemoryLoader:
    """Tests for Anthos memory metric loaders."""
    
    def test_memory_loader_uses_anthos_metric(self, mock_prometheus, sample_object):
        """Test that AnthosMemoryLoader uses kubernetes.io/anthos/* metric."""
        loader = AnthosMemoryLoader(mock_prometheus, "Anthos Metrics")
        query = loader.get_query(sample_object, "2h", "1m")
        
        # Verify Anthos metric name is used
        assert 'kubernetes.io/anthos/container/memory/used_bytes' in query
        assert 'kubernetes.io/container/memory/used_bytes' not in query
        
        # Verify monitored_resource label is present
        assert "monitored_resource" in query and "k8s_container" in query
        
        # Note: AnthosMemoryLoader base query uses max() aggregation
        # max_over_time is only used in AnthosMaxMemoryLoader
        assert 'max(' in query
    
    def test_max_memory_loader_query(self, mock_prometheus, sample_object):
        """Test AnthosMaxMemoryLoader generates correct query."""
        loader = AnthosMaxMemoryLoader(mock_prometheus, "Anthos Metrics")
        query = loader.get_query(sample_object, "2h", "1m")
        
        # Verify Anthos metric is used
        assert 'kubernetes.io/anthos/container/memory/used_bytes' in query
        assert "monitored_resource" in query and "k8s_container" in query
        
        # Verify max_over_time is used (Anthos convention)
        assert 'max_over_time' in query
    
    def test_memory_amount_loader_query(self, mock_prometheus, sample_object):
        """Test AnthosMemoryAmountLoader generates correct query."""
        loader = AnthosMemoryAmountLoader(mock_prometheus, "Anthos Metrics")
        query = loader.get_query(sample_object, "2h", "1m")
        
        # Verify Anthos metric is used
        assert 'kubernetes.io/anthos/container/memory/used_bytes' in query
        assert "monitored_resource" in query and "k8s_container" in query
        
        # Verify it's counting containers
        assert 'count' in query.lower()


class TestQuerySyntaxValidation:
    """Tests to validate that Anthos queries have no syntax errors."""
    
    def test_no_syntax_errors_in_queries(self, mock_prometheus, sample_object):
        """Verify all Anthos loaders generate syntactically valid queries."""
        loaders = [
            AnthosCPULoader(mock_prometheus, "Anthos"),
            AnthosCPUAmountLoader(mock_prometheus, "Anthos"),
            AnthosMemoryLoader(mock_prometheus, "Anthos"),
            AnthosMaxMemoryLoader(mock_prometheus, "Anthos"),
            AnthosMemoryAmountLoader(mock_prometheus, "Anthos"),
        ]
        
        # Add percentile loader (factory function)
        PercentileLoaderClass = AnthosPercentileCPULoader(95)
        loaders.append(PercentileLoaderClass(mock_prometheus, "Anthos"))
        
        for loader in loaders:
            query = loader.get_query(sample_object, "2h", "1m")
            
            # Basic syntax checks
            assert query.count('(') == query.count(')'), f"Unbalanced parentheses in {loader.__class__.__name__}"
            assert query.count('{') == query.count('}'), f"Unbalanced braces in {loader.__class__.__name__}"
            assert query.count('[') == query.count(']'), f"Unbalanced brackets in {loader.__class__.__name__}"
            
            # Verify UTF-8 syntax is used
            assert '{"__name__"=' in query, f"Missing UTF-8 syntax in {loader.__class__.__name__}"
            
            # Verify monitored_resource label is present
            assert "monitored_resource" in query and "k8s_container" in query, f"Missing monitored_resource in {loader.__class__.__name__}"


class TestAnthosMetricsService:
    """Tests for AnthosMetricsService configuration."""
    
    def test_loader_mapping(self):
        """Test that AnthosMetricsService has correct loader mapping."""
        from robusta_krr.core.integrations.prometheus.metrics_service.anthos_metrics_service import (
            AnthosMetricsService
        )
        
        mapping = AnthosMetricsService.LOADER_MAPPING
        
        # Verify CPU loaders are mapped
        assert "CPULoader" in mapping
        assert mapping["CPULoader"] == AnthosCPULoader
        
        assert "PercentileCPULoader" in mapping
        assert mapping["PercentileCPULoader"] == AnthosPercentileCPULoader
        
        assert "CPUAmountLoader" in mapping
        assert mapping["CPUAmountLoader"] == AnthosCPUAmountLoader
        
        # Verify Memory loaders are mapped
        assert "MemoryLoader" in mapping
        assert mapping["MemoryLoader"] == AnthosMemoryLoader
        
        assert "MaxMemoryLoader" in mapping
        assert mapping["MaxMemoryLoader"] == AnthosMaxMemoryLoader
        
        assert "MemoryAmountLoader" in mapping
        assert mapping["MemoryAmountLoader"] == AnthosMemoryAmountLoader
        
        # Verify unsupported loader is marked as None
        assert "MaxOOMKilledMemoryLoader" in mapping
        assert mapping["MaxOOMKilledMemoryLoader"] is None
