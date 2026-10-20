import pytest
import numpy as np
from datetime import datetime, timedelta

from robusta_krr.core.abstract.strategies import MetricsPodData, K8sObjectData, PodData
from robusta_krr.core.integrations.prometheus.metrics.memory import (
    JVMMemoryLoader,
    MaxJVMMemoryLoader,
    JVMMemoryAmountLoader,
    JVMDetector,
)
from robusta_krr.strategies.simple import SimpleStrategy, SimpleStrategySettings


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
def mock_jvm_metrics_data():
    return {
        "JVMDetector": {
            "test-app-pod-1": np.array([
                [1625097600, 1000000],  # 1MB
                [1625097900, 2000000],  # 2MB
                [1625098200, 1500000],  # 1.5MB
            ]),
            "test-app-pod-2": np.array([
                [1625097600, 1200000],  # 1.2MB
                [1625097900, 1800000],  # 1.8MB
                [1625098200, 1600000],  # 1.6MB
            ]),
        },
        "MaxJVMMemoryLoader": {
            "test-app-pod-1": np.array([
                [1625097600, 1000000],  # 1MB
                [1625097900, 2000000],  # 2MB
                [1625098200, 1500000],  # 1.5MB
            ]),
            "test-app-pod-2": np.array([
                [1625097600, 1200000],  # 1.2MB
                [1625097900, 1800000],  # 1.8MB
                [1625098200, 1600000],  # 1.6MB
            ]),
        },
        "JVMMemoryAmountLoader": {
            "test-app-pod-1": np.array([[1625098200, 3]]),  # 3 data points
            "test-app-pod-2": np.array([[1625098200, 3]]),  # 3 data points
        },
    }


@pytest.fixture
def mock_non_jvm_metrics_data():
    return {
        "JVMDetector": {},  # Empty JVM metrics
        "MaxMemoryLoader": {
            "test-app-pod-1": np.array([
                [1625097600, 1000000],  # 1MB
                [1625097900, 2000000],  # 2MB
                [1625098200, 1500000],  # 1.5MB
            ]),
            "test-app-pod-2": np.array([
                [1625097600, 1200000],  # 1.2MB
                [1625097900, 1800000],  # 1.8MB
                [1625098200, 1600000],  # 1.6MB
            ]),
        },
        "MemoryAmountLoader": {
            "test-app-pod-1": np.array([[1625098200, 3]]),  # 3 data points
            "test-app-pod-2": np.array([[1625098200, 3]]),  # 3 data points
        },
    }


def test_jvm_detection(mock_pod_data, mock_jvm_metrics_data):
    strategy = SimpleStrategy(SimpleStrategySettings())
    result = strategy.run(mock_jvm_metrics_data, mock_pod_data)
    
    # Check if JVM application is detected
    assert result["Memory"].info == "JVM application detected"
    
    # Check if memory recommendation uses JVM buffer percentage
    max_memory = 2000000  # 2MB (max from mock data)
    expected_memory = max_memory * (1 + strategy.settings.jvm_memory_buffer_percentage / 100)
    assert result["Memory"].request == expected_memory


def test_non_jvm_detection(mock_pod_data, mock_non_jvm_metrics_data):
    strategy = SimpleStrategy(SimpleStrategySettings())
    result = strategy.run(mock_non_jvm_metrics_data, mock_pod_data)
    
    # Check if non-JVM application is detected
    assert result["Memory"].info is None
    
    # Check if memory recommendation uses regular buffer percentage
    max_memory = 2000000  # 2MB (max from mock data)
    expected_memory = max_memory * (1 + strategy.settings.memory_buffer_percentage / 100)
    assert result["Memory"].request == expected_memory


def test_jvm_with_oomkill(mock_pod_data, mock_jvm_metrics_data):
    # Add OOMKill data
    mock_jvm_metrics_data["MaxOOMKilledMemoryLoader"] = {
        "test-app-pod-1": np.array([[1625098200, 2500000]]),  # 2.5MB
    }
    
    strategy = SimpleStrategy(SimpleStrategySettings(use_oomkill_data=True))
    result = strategy.run(mock_jvm_metrics_data, mock_pod_data)
    
    # Check if both JVM and OOMKill are detected
    assert "JVM application detected" in result["Memory"].info
    assert "OOMKill detected" in result["Memory"].info
    
    # Check if memory recommendation uses OOMKill value with buffer
    oomkill_memory = 2500000  # 2.5MB (from OOMKill data)
    expected_memory = oomkill_memory * (1 + strategy.settings.oom_memory_buffer_percentage / 100)
    assert result["Memory"].request == expected_memory


def test_jvm_with_hpa(mock_pod_data, mock_jvm_metrics_data):
    # Add HPA data
    mock_pod_data.hpa = type("HPA", (), {
        "target_memory_utilization_percentage": 80
    })
    
    strategy = SimpleStrategy(SimpleStrategySettings())
    result = strategy.run(mock_jvm_metrics_data, mock_pod_data)
    
    # Check if HPA is detected
    assert result["Memory"].info == "HPA detected"
    assert result["Memory"].request is None


def test_jvm_with_hpa_override(mock_pod_data, mock_jvm_metrics_data):
    # Add HPA data
    mock_pod_data.hpa = type("HPA", (), {
        "target_memory_utilization_percentage": 80
    })
    
    strategy = SimpleStrategy(SimpleStrategySettings(allow_hpa=True))
    result = strategy.run(mock_jvm_metrics_data, mock_pod_data)
    
    # Check if JVM is detected and HPA is ignored
    assert result["Memory"].info == "JVM application detected"
    assert result["Memory"].request is not None


def test_jvm_custom_buffer_percentage(mock_pod_data, mock_jvm_metrics_data):
    custom_buffer = 40
    strategy = SimpleStrategy(SimpleStrategySettings(jvm_memory_buffer_percentage=custom_buffer))
    result = strategy.run(mock_jvm_metrics_data, mock_pod_data)
    
    # Check if memory recommendation uses custom JVM buffer percentage
    max_memory = 2000000  # 2MB (max from mock data)
    expected_memory = max_memory * (1 + custom_buffer / 100)
    assert result["Memory"].request == expected_memory 