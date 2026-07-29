import pytest
from datetime import datetime, timedelta
import numpy as np

from robusta_krr.core.integrations.prometheus.metrics.memory import (
    JVMMemoryLoader,
    MaxJVMMemoryLoader,
    JVMMemoryAmountLoader,
    JVMDetector,
)
from robusta_krr.core.models.objects import K8sObjectData, PodData


@pytest.fixture
def mock_pod_data():
    return K8sObjectData(
        name="test-app",
        namespace="default",
        kind="Deployment",
        container="app",
        pods=[
            PodData(name="test-app-pod-1", namespace="default"),
            PodData(name="test-app-pod-2", namespace="default"),
        ],
    )


@pytest.fixture
def mock_prometheus_response():
    return {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {
                        "container": "app",
                        "pod": "test-app-pod-1",
                        "job": "kubernetes-pods",
                    },
                    "values": [
                        [1625097600, "1000000"],  # 1MB
                        [1625097900, "2000000"],  # 2MB
                        [1625098200, "1500000"],  # 1.5MB
                    ],
                },
                {
                    "metric": {
                        "container": "app",
                        "pod": "test-app-pod-2",
                        "job": "kubernetes-pods",
                    },
                    "values": [
                        [1625097600, "1200000"],  # 1.2MB
                        [1625097900, "1800000"],  # 1.8MB
                        [1625098200, "1600000"],  # 1.6MB
                    ],
                },
            ],
        },
    }


def test_jvm_memory_loader_query(mock_pod_data):
    loader = JVMMemoryLoader()
    query = loader.get_query(mock_pod_data, "1h", "1m")
    
    assert "jvm_memory_bytes_used" in query
    assert "area=\"heap\"" in query
    assert "test-app-pod-1|test-app-pod-2" in query
    assert "namespace=\"default\"" in query
    assert "container=\"app\"" in query


def test_max_jvm_memory_loader_query(mock_pod_data):
    loader = MaxJVMMemoryLoader()
    query = loader.get_query(mock_pod_data, "1h", "1m")
    
    assert "jvm_memory_bytes_used" in query
    assert "area=\"heap\"" in query
    assert "max_over_time" in query
    assert "test-app-pod-1|test-app-pod-2" in query


def test_jvm_memory_amount_loader_query(mock_pod_data):
    loader = JVMMemoryAmountLoader()
    query = loader.get_query(mock_pod_data, "1h", "1m")
    
    assert "jvm_memory_bytes_used" in query
    assert "area=\"heap\"" in query
    assert "count_over_time" in query
    assert "test-app-pod-1|test-app-pod-2" in query


def test_jvm_detector_query(mock_pod_data):
    loader = JVMDetector()
    query = loader.get_query(mock_pod_data, "1h", "1m")
    
    assert "jvm_memory_bytes_used" in query
    assert "test-app-pod-1|test-app-pod-2" in query


def test_jvm_memory_loader_parse_response(mock_prometheus_response):
    loader = JVMMemoryLoader()
    result = loader.parse_response(mock_prometheus_response)
    
    assert len(result) == 2
    assert "test-app-pod-1" in result
    assert "test-app-pod-2" in result
    
    # Check if values are properly converted to numpy arrays
    pod1_values = result["test-app-pod-1"]
    assert isinstance(pod1_values, np.ndarray)
    assert pod1_values.shape == (3, 2)  # 3 timestamps, 2 values each
    assert np.max(pod1_values[:, 1]) == 2000000  # Max value should be 2MB


def test_max_jvm_memory_loader_parse_response(mock_prometheus_response):
    loader = MaxJVMMemoryLoader()
    result = loader.parse_response(mock_prometheus_response)
    
    assert len(result) == 2
    assert "test-app-pod-1" in result
    assert "test-app-pod-2" in result
    
    # Check if values are properly converted to numpy arrays
    pod1_values = result["test-app-pod-1"]
    assert isinstance(pod1_values, np.ndarray)
    assert pod1_values.shape == (3, 2)
    assert np.max(pod1_values[:, 1]) == 2000000  # Max value should be 2MB


def test_jvm_memory_amount_loader_parse_response(mock_prometheus_response):
    loader = JVMMemoryAmountLoader()
    result = loader.parse_response(mock_prometheus_response)
    
    assert len(result) == 2
    assert "test-app-pod-1" in result
    assert "test-app-pod-2" in result
    
    # Check if values are properly converted to numpy arrays
    pod1_values = result["test-app-pod-1"]
    assert isinstance(pod1_values, np.ndarray)
    assert pod1_values.shape == (3, 2)
    assert np.sum(pod1_values[:, 1]) == 3  # Should count 3 data points


def test_jvm_detector_parse_response(mock_prometheus_response):
    loader = JVMDetector()
    result = loader.parse_response(mock_prometheus_response)
    
    assert len(result) == 2
    assert "test-app-pod-1" in result
    assert "test-app-pod-2" in result
    
    # Check if values are properly converted to numpy arrays
    pod1_values = result["test-app-pod-1"]
    assert isinstance(pod1_values, np.ndarray)
    assert pod1_values.shape == (3, 2)
    assert np.max(pod1_values[:, 1]) == 2000000  # Max value should be 2MB 