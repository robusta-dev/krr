"""Tests for AI-Assisted strategy."""

import json
from unittest.mock import Mock, patch, MagicMock
import numpy as np
import pytest

from robusta_krr.core.abstract.strategies import MetricsPodData, ResourceType
from robusta_krr.core.models.objects import K8sObjectData, PodData, HPAData
from robusta_krr.core.models.allocations import ResourceAllocations
from robusta_krr.strategies.ai_assisted import AiAssistedStrategy, AiAssistedStrategySettings
from robusta_krr.strategies import ai_prompts


# Mock global_settings for tests
@pytest.fixture(autouse=True)
def mock_global_settings():
    """Mock global_settings with default values."""
    with patch('robusta_krr.strategies.ai_assisted.global_settings') as mock_settings:
        mock_settings.cpu_min_value = 10  # 10 millicores
        mock_settings.memory_min_value = 100  # 100 MB
        yield mock_settings


# Fixtures

@pytest.fixture
def sample_history_data() -> MetricsPodData:
    """Create sample Prometheus metrics data."""
    # CPU data: 100 time points with values around 0.2 cores
    cpu_timestamps = np.linspace(0, 3600, 100)
    cpu_values = np.random.normal(0.2, 0.05, 100)
    cpu_data = np.column_stack([cpu_timestamps, cpu_values])
    
    # Memory data: max memory usage around 500MB
    memory_values = np.random.normal(500 * 1024 * 1024, 50 * 1024 * 1024, 10)
    memory_timestamps = np.linspace(0, 3600, 10)
    memory_data = np.column_stack([memory_timestamps, memory_values])
    
    # Data point counts
    cpu_count = np.array([[0, 100]])  # 100 data points
    memory_count = np.array([[0, 100]])
    
    return {
        "CPULoader": {
            "test-pod-1": cpu_data,
            "test-pod-2": cpu_data * 1.1,  # Slightly higher
        },
        "MaxMemoryLoader": {
            "test-pod-1": memory_data,
            "test-pod-2": memory_data * 0.9,  # Slightly lower
        },
        "CPUAmountLoader": {
            "test-pod-1": cpu_count,
            "test-pod-2": cpu_count,
        },
        "MemoryAmountLoader": {
            "test-pod-1": memory_count,
            "test-pod-2": memory_count,
        },
    }


@pytest.fixture
def sample_object_data() -> K8sObjectData:
    """Create sample Kubernetes object data."""
    return K8sObjectData(
        cluster="test-cluster",
        name="test-deployment",
        container="test-container",
        namespace="default",
        kind="Deployment",
        pods=[
            PodData(name="test-pod-1", deleted=False),
            PodData(name="test-pod-2", deleted=False),
        ],
        hpa=None,
        allocations=ResourceAllocations(
            requests={"cpu": "100m", "memory": "256Mi"},
            limits={"cpu": "500m", "memory": "512Mi"},
        ),
        warnings=set(),
        labels={"app": "test"},
        annotations={},
    )


@pytest.fixture
def mock_ai_response() -> dict:
    """Create mock AI response."""
    return {
        "cpu_request": 0.25,
        "cpu_limit": None,
        "memory_request": 536870912,  # 512Mi
        "memory_limit": 536870912,
        "reasoning": "Based on p95 CPU at 0.18 cores with low variance, 0.25 cores provides safe headroom.",
        "confidence": 85
    }


# Test Stats Extraction

class TestStatsExtraction:
    """Test comprehensive stats extraction from Prometheus data."""
    
    def test_extract_cpu_stats(self, sample_history_data, sample_object_data):
        """Test CPU statistics extraction."""
        stats = ai_prompts.extract_comprehensive_stats(
            sample_history_data,
            sample_object_data
        )
        
        assert "cpu" in stats
        cpu = stats["cpu"]
        
        # Check percentiles
        assert "percentiles" in cpu
        assert "p50" in cpu["percentiles"]
        assert "p95" in cpu["percentiles"]
        assert "p99" in cpu["percentiles"]
        
        # Check aggregate stats
        assert "max" in cpu
        assert "mean" in cpu
        assert "std" in cpu
        assert "trend_slope" in cpu
        assert "spike_count" in cpu
        
        # Values should be in reasonable range
        assert 0 < cpu["mean"] < 1.0  # Should be around 0.2
        assert cpu["max"] > cpu["mean"]
    
    def test_extract_memory_stats(self, sample_history_data, sample_object_data):
        """Test memory statistics extraction."""
        stats = ai_prompts.extract_comprehensive_stats(
            sample_history_data,
            sample_object_data
        )
        
        assert "memory" in stats
        memory = stats["memory"]
        
        assert "max" in memory
        assert "mean" in memory
        assert "std" in memory
        assert "oomkill_detected" in memory
        
        # Memory should be around 500MB
        assert 400 * 1024 * 1024 < memory["mean"] < 600 * 1024 * 1024
    
    def test_extract_with_oomkill(self, sample_history_data, sample_object_data):
        """Test OOMKill detection."""
        # Add OOMKill data
        sample_history_data["MaxOOMKilledMemoryLoader"] = {
            "test-pod-1": np.array([[0, 600 * 1024 * 1024]])  # 600MB OOMKill
        }
        
        stats = ai_prompts.extract_comprehensive_stats(
            sample_history_data,
            sample_object_data
        )
        
        assert stats["memory"]["oomkill_detected"] is True
        assert "oomkill_max_value" in stats["memory"]
        assert stats["memory"]["oomkill_max_value"] > 0
    
    def test_extract_workload_info(self, sample_history_data, sample_object_data):
        """Test workload information extraction."""
        stats = ai_prompts.extract_comprehensive_stats(
            sample_history_data,
            sample_object_data
        )
        
        assert stats["workload"]["namespace"] == "default"
        assert stats["workload"]["name"] == "test-deployment"
        assert stats["workload"]["kind"] == "Deployment"
        assert stats["workload"]["container"] == "test-container"
        
        assert stats["pods"]["current_count"] == 2
        assert stats["pods"]["deleted_count"] == 0


# Test Prompt Formatting

class TestPromptFormatting:
    """Test prompt generation for different providers."""
    
    def test_format_messages_openai(self, sample_history_data, sample_object_data):
        """Test OpenAI message format."""
        settings = AiAssistedStrategySettings()
        stats = ai_prompts.extract_comprehensive_stats(
            sample_history_data,
            sample_object_data
        )
        
        messages = ai_prompts.format_messages("openai", stats, sample_object_data, settings)
        
        assert isinstance(messages, list)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "cpu" in messages[1]["content"].lower()
        assert "memory" in messages[1]["content"].lower()
    
    def test_format_messages_anthropic(self, sample_history_data, sample_object_data):
        """Test Anthropic message format."""
        settings = AiAssistedStrategySettings()
        stats = ai_prompts.extract_comprehensive_stats(
            sample_history_data,
            sample_object_data
        )
        
        messages = ai_prompts.format_messages("anthropic", stats, sample_object_data, settings)
        
        assert isinstance(messages, list)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
    
    def test_format_messages_gemini(self, sample_history_data, sample_object_data):
        """Test Gemini message format (string)."""
        settings = AiAssistedStrategySettings()
        stats = ai_prompts.extract_comprehensive_stats(
            sample_history_data,
            sample_object_data
        )
        
        messages = ai_prompts.format_messages("gemini", stats, sample_object_data, settings)
        
        assert isinstance(messages, str)
        assert "cpu" in messages.lower()
        assert "memory" in messages.lower()
    
    def test_compact_mode(self, sample_history_data, sample_object_data):
        """Test compact mode reduces prompt length."""
        stats = ai_prompts.extract_comprehensive_stats(
            sample_history_data,
            sample_object_data
        )
        
        settings_full = AiAssistedStrategySettings(ai_compact_mode=False)
        settings_compact = AiAssistedStrategySettings(ai_compact_mode=True)
        
        full_prompt = ai_prompts.get_user_prompt(stats, compact=False)
        compact_prompt = ai_prompts.get_user_prompt(stats, compact=True)
        
        # Compact should be significantly shorter
        assert len(compact_prompt) < len(full_prompt)
        assert len(compact_prompt) < len(full_prompt) * 0.7  # At least 30% reduction


# Test Provider Integration

class TestProviderIntegration:
    """Test AI provider integrations with mocked API calls."""
    
    @patch('requests.post')
    def test_openai_provider(self, mock_post, mock_ai_response):
        """Test OpenAI provider API call."""
        from robusta_krr.core.integrations.ai import get_provider
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(mock_ai_response)
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        provider = get_provider("openai", "test-key", "gpt-4o-mini")
        result = provider.analyze_metrics([{"role": "user", "content": "test"}])
        
        assert result["cpu_request"] == 0.25
        assert result["confidence"] == 85
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_gemini_provider(self, mock_post, mock_ai_response):
        """Test Gemini provider API call."""
        from robusta_krr.core.integrations.ai import get_provider
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": json.dumps(mock_ai_response)}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_response
        
        provider = get_provider("gemini", "test-key", "gemini-2.0-flash-exp")
        result = provider.analyze_metrics("test prompt")
        
        assert result["cpu_request"] == 0.25
    
    @patch('requests.post')
    def test_json_extraction_from_markdown(self, mock_post):
        """Test JSON extraction from markdown code blocks."""
        from robusta_krr.core.integrations.ai import get_provider
        
        # Response with JSON in markdown
        markdown_response = """
        Here are my recommendations:
        
        ```json
        {
          "cpu_request": 0.5,
          "cpu_limit": null,
          "memory_request": 1073741824,
          "memory_limit": 1073741824,
          "reasoning": "Test",
          "confidence": 90
        }
        ```
        
        I hope this helps!
        """
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": markdown_response}}]
        }
        mock_post.return_value = mock_response
        
        provider = get_provider("openai", "test-key", "gpt-4o-mini")
        result = provider.analyze_metrics([{"role": "user", "content": "test"}])
        
        assert result["cpu_request"] == 0.5
        assert result["confidence"] == 90


# Test Auto-Detection

class TestAutoDetection:
    """Test AI provider auto-detection from environment."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-openai-key'})
    def test_detect_openai(self):
        """Test OpenAI detection from env var."""
        settings = AiAssistedStrategySettings()
        strategy = AiAssistedStrategy(settings)
        
        assert strategy.provider_name == "openai"
        assert strategy.model_name == "gpt-4o-mini"
        assert strategy.api_key == "test-openai-key"
    
    @patch.dict('os.environ', {'GEMINI_API_KEY': 'test-gemini-key'})
    def test_detect_gemini(self):
        """Test Gemini detection from env var."""
        settings = AiAssistedStrategySettings()
        strategy = AiAssistedStrategy(settings)
        
        assert strategy.provider_name == "gemini"
        assert strategy.model_name == "gemini-2.0-flash-exp"
    
    @patch.dict('os.environ', {}, clear=True)
    def test_no_provider_raises_error(self):
        """Test error when no provider is available."""
        settings = AiAssistedStrategySettings()
        
        with pytest.raises(ValueError, match="No AI provider API key found"):
            AiAssistedStrategy(settings)
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_override_with_settings(self):
        """Test overriding auto-detection with explicit settings."""
        from pydantic import SecretStr
        
        settings = AiAssistedStrategySettings(
            ai_provider="anthropic",
            ai_model="claude-3-5-haiku",
            ai_api_key=SecretStr("override-key")
        )
        strategy = AiAssistedStrategy(settings)
        
        assert strategy.provider_name == "anthropic"
        assert strategy.model_name == "claude-3-5-haiku"
        assert strategy.api_key == "override-key"


# Test Validation

class TestValidation:
    """Test recommendation validation and constraints."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('requests.post')
    def test_min_max_constraints(self, mock_post, sample_history_data, sample_object_data):
        """Test min/max constraints are applied."""
        # Mock AI returning extreme values
        extreme_response = {
            "cpu_request": 0.001,  # Below minimum
            "cpu_limit": 20.0,  # Above maximum
            "memory_request": 1000,  # Below minimum
            "memory_limit": 100000000000000,  # Above maximum
            "reasoning": "Test extreme values",
            "confidence": 50
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(extreme_response)}}]
        }
        mock_post.return_value = mock_response
        
        settings = AiAssistedStrategySettings()
        strategy = AiAssistedStrategy(settings)
        result = strategy.run(sample_history_data, sample_object_data)
        
        # CPU should be clamped to min (0.01) and max (16.0)
        assert result[ResourceType.CPU].request >= 0.01
        assert result[ResourceType.CPU].limit <= 16.0
        
        # Memory should be clamped to min (100Mi) and max (64Gi)
        assert result[ResourceType.Memory].request >= 100 * 1024 * 1024
        assert result[ResourceType.Memory].limit <= 64 * 1024 * 1024 * 1024


# Test Output Format

class TestOutputFormat:
    """Test that output is compatible with existing formatters."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('requests.post')
    def test_output_format(self, mock_post, sample_history_data, sample_object_data, mock_ai_response):
        """Test output format matches expected RunResult structure."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": json.dumps(mock_ai_response)}}]
        }
        mock_post.return_value = mock_response
        
        settings = AiAssistedStrategySettings()
        strategy = AiAssistedStrategy(settings)
        result = strategy.run(sample_history_data, sample_object_data)
        
        # Check structure
        assert ResourceType.CPU in result
        assert ResourceType.Memory in result
        
        # Check CPU recommendation
        cpu_rec = result[ResourceType.CPU]
        assert cpu_rec.request is not None
        assert isinstance(cpu_rec.request, float)
        assert cpu_rec.info is not None
        assert "AI:" in cpu_rec.info
        assert "conf:" in cpu_rec.info
        
        # Check Memory recommendation
        mem_rec = result[ResourceType.Memory]
        assert mem_rec.request is not None
        assert isinstance(mem_rec.request, (int, float))


# Test Error Handling

class TestErrorHandling:
    """Test error handling and fallback behavior."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    @patch('requests.post')
    def test_ai_error_returns_undefined(self, mock_post, sample_history_data, sample_object_data):
        """Test that AI errors result in undefined recommendations."""
        # Mock API error
        mock_post.side_effect = Exception("API Error")
        
        settings = AiAssistedStrategySettings()
        strategy = AiAssistedStrategy(settings)
        result = strategy.run(sample_history_data, sample_object_data)
        
        # Should return undefined for both resources
        assert np.isnan(result[ResourceType.CPU].request)
        assert np.isnan(result[ResourceType.Memory].request)
        assert result[ResourceType.CPU].info == "AI error"
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'})
    def test_insufficient_data(self, sample_object_data):
        """Test handling of insufficient data points."""
        # Create minimal data (below points_required threshold)
        minimal_data = {
            "CPULoader": {"test-pod": np.array([[0, 0.1]])},
            "MaxMemoryLoader": {"test-pod": np.array([[0, 100000000]])},
            "CPUAmountLoader": {"test-pod": np.array([[0, 10]])},  # Only 10 points
            "MemoryAmountLoader": {"test-pod": np.array([[0, 10]])},
        }
        
        settings = AiAssistedStrategySettings(points_required=100)
        strategy = AiAssistedStrategy(settings)
        result = strategy.run(minimal_data, sample_object_data)
        
        assert result[ResourceType.CPU].info == "Not enough data"
        assert result[ResourceType.Memory].info == "Not enough data"
