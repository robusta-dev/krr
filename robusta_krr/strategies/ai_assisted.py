"""AI-Assisted resource recommendation strategy."""

import logging
import os
import textwrap
from typing import Optional

import pydantic as pd

from robusta_krr.core.abstract.strategies import (
    BaseStrategy,
    K8sObjectData,
    MetricsPodData,
    ResourceRecommendation,
    ResourceType,
    RunResult,
    StrategySettings,
)
from robusta_krr.core.integrations.prometheus.metrics import (
    CPUAmountLoader,
    CPULoader,
    MaxMemoryLoader,
    MaxOOMKilledMemoryLoader,
    MemoryAmountLoader,
    PrometheusMetric,
)
from robusta_krr.core.models.config import settings as global_settings
from robusta_krr.strategies import ai_prompts

logger = logging.getLogger("krr")


class AiAssistedStrategySettings(StrategySettings):
    """Settings for AI-Assisted strategy."""
    
    ai_provider: Optional[str] = pd.Field(
        None,
        description="AI provider (openai/gemini/anthropic/ollama). Auto-detected from env vars if not specified."
    )
    ai_model: Optional[str] = pd.Field(
        None,
        description="AI model name. Uses provider default if not specified."
    )
    ai_api_key: Optional[pd.SecretStr] = pd.Field(
        None,
        description="AI API key. Falls back to env vars: OPENAI_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY."
    )
    ai_temperature: float = pd.Field(
        0.3,
        ge=0,
        le=2,
        description="AI temperature for response randomness (0=deterministic, 2=creative)."
    )
    ai_max_tokens: int = pd.Field(
        2000,
        ge=100,
        le=8000,
        description="Maximum tokens in AI response."
    )
    ai_compact_mode: bool = pd.Field(
        False,
        description="Compress statistics in prompt to reduce token usage (~60% reduction)."
    )
    ai_exclude_simple_reference: bool = pd.Field(
        False,
        description="Exclude Simple strategy baseline from AI prompt (by default it is included)."
    )
    ai_timeout: int = pd.Field(
        60,
        ge=10,
        le=300,
        description="Timeout for AI API calls in seconds."
    )
    
    # Standard strategy settings
    cpu_percentile: float = pd.Field(
        95,
        gt=0,
        le=100,
        description="CPU percentile for reference comparison with Simple strategy."
    )
    memory_buffer_percentage: float = pd.Field(
        15,
        gt=0,
        description="Memory buffer percentage for reference comparison with Simple strategy."
    )
    points_required: int = pd.Field(
        100,
        ge=1,
        description="The number of data points required to make a recommendation."
    )
    allow_hpa: bool = pd.Field(
        False,
        description="Whether to calculate recommendations even when there is an HPA scaler defined."
    )
    use_oomkill_data: bool = pd.Field(
        True,
        description="Whether to include OOMKill data in analysis."
    )


class AiAssistedStrategy(BaseStrategy[AiAssistedStrategySettings]):
    """AI-Assisted resource recommendation strategy.
    
    This strategy uses Large Language Models to analyze historical resource usage
    metrics and provide intelligent recommendations based on patterns, trends,
    and anomalies in the data.
    """
    
    display_name = "ai-assisted"
    rich_console = True
    
    def __init__(self, settings: AiAssistedStrategySettings):
        """Initialize the AI-Assisted strategy.
        
        Args:
            settings: Strategy settings
            
        Raises:
            ValueError: If no AI provider API key is found
        """
        super().__init__(settings)
        
        # Auto-detect AI provider if not specified
        self.provider_name, self.model_name, self.api_key = self._detect_provider()
        
        # Initialize AI provider
        from robusta_krr.core.integrations.ai import get_provider
        
        try:
            self.provider = get_provider(
                self.provider_name,
                self.api_key,
                self.model_name,
                timeout=self.settings.ai_timeout
            )
            logger.info(
                f"AI-Assisted strategy initialized with {self.provider_name} "
                f"(model: {self.model_name})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize AI provider: {e}")
            raise
    
    def _detect_provider(self) -> tuple[str, str, str]:
        """Detect AI provider from settings or environment variables.
        
        Returns:
            Tuple of (provider_name, model_name, api_key)
            
        Raises:
            ValueError: If no provider can be detected
        """
        # Check if explicitly set in settings
        if self.settings.ai_provider and self.settings.ai_api_key:
            provider = self.settings.ai_provider.lower()
            api_key = self.settings.ai_api_key.get_secret_value()
            
            # Use specified model or default for provider
            model = self.settings.ai_model or self._get_default_model(provider)
            
            return provider, model, api_key
        
        # Auto-detect from environment variables (priority order)
        detection_order = [
            ("OPENAI_API_KEY", "openai", "gpt-4o-mini"),
            ("GEMINI_API_KEY", "gemini", "gemini-2.0-flash-exp"),
            ("GOOGLE_API_KEY", "gemini", "gemini-2.0-flash-exp"),
            ("ANTHROPIC_API_KEY", "anthropic", "claude-3-5-sonnet-20241022"),
            ("OLLAMA_HOST", "ollama", "llama3.2"),
        ]
        
        for env_var, provider, default_model in detection_order:
            api_key = os.environ.get(env_var)
            if api_key:
                # Override with explicit settings if provided
                final_provider = self.settings.ai_provider or provider
                final_model = self.settings.ai_model or default_model
                
                # Override API key if explicitly set
                if self.settings.ai_api_key:
                    api_key = self.settings.ai_api_key.get_secret_value()
                
                logger.info(
                    f"Auto-detected AI provider: {final_provider} "
                    f"(from {env_var} env var)"
                )
                
                return final_provider, final_model, api_key
        
        # No provider found
        raise ValueError(
            "No AI provider API key found. Please set one of the following:\n"
            "  - OPENAI_API_KEY environment variable\n"
            "  - GEMINI_API_KEY or GOOGLE_API_KEY environment variable\n"
            "  - ANTHROPIC_API_KEY environment variable\n"
            "  - OLLAMA_HOST environment variable\n"
            "Or use --ai-provider and --ai-api-key flags to specify explicitly."
        )
    
    def _get_default_model(self, provider: str) -> str:
        """Get default model for a provider.
        
        Args:
            provider: Provider name
            
        Returns:
            Default model name
        """
        defaults = {
            "openai": "gpt-4o-mini",
            "gemini": "gemini-2.0-flash-exp",
            "anthropic": "claude-3-5-sonnet-20241022",
            "ollama": "llama3.2",
        }
        return defaults.get(provider.lower(), "unknown")
    
    @property
    def metrics(self) -> list[type[PrometheusMetric]]:
        """Define which Prometheus metrics to collect."""
        metrics = [
            CPULoader,
            MaxMemoryLoader,
            CPUAmountLoader,
            MemoryAmountLoader,
        ]
        
        if self.settings.use_oomkill_data:
            metrics.append(MaxOOMKilledMemoryLoader)
        
        return metrics
    
    @property
    def description(self) -> str:
        """Get strategy description for CLI help."""
        return textwrap.dedent(f"""\
            [bold]AI-Assisted Resource Recommendations[/bold]
            
            Uses {self.provider_name} ({self.model_name}) to analyze historical metrics
            
            [underline]How it works:[/underline]
            • Analyzes CPU percentiles (50/75/90/95/99), trends, and spike patterns
            • Examines memory usage patterns, max values, and OOM events
            • Uses linear regression to detect increasing/decreasing trends
            • Considers current allocations and HPA configuration
            • Provides confidence scores and reasoning for recommendations
            
            [underline]Data analyzed:[/underline]
            • CPU: percentiles, mean, std dev, trend slope, spike count
            • Memory: max, mean, std dev, OOM kills
            • Pod info: count, health status
            • Workload context: HPA settings, current allocations
            • History: {self.settings.history_duration} hours
            • Step: {self.settings.timeframe_duration} minutes
            
            [underline]Configuration:[/underline]
            • Temperature: {self.settings.ai_temperature} (0=deterministic, 2=creative)
            • Max tokens: {self.settings.ai_max_tokens}
            • Compact mode: {"enabled" if self.settings.ai_compact_mode else "disabled"} (reduces token usage ~60%)
            • Simple reference: {"excluded" if self.settings.ai_exclude_simple_reference else "included"}
            • Points required: {self.settings.points_required}
            
            [underline]Cost control:[/underline]
            Use --ai-compact-mode to reduce token usage from ~1500-2000 to ~600-800 tokens per workload.
            API costs vary by provider - monitor usage carefully for large clusters.
            
            [underline]Customization:[/underline]
            Override with: --ai-provider, --ai-model, --ai-api-key, --ai-temperature, --ai-compact-mode
            
            Learn more: [underline]https://github.com/robusta-dev/krr#ai-assisted-strategy[/underline]
        """)
    
    def run(self, history_data: MetricsPodData, object_data: K8sObjectData) -> RunResult:
        """Run the AI-Assisted strategy to calculate recommendations.
        
        Args:
            history_data: Historical metrics data from Prometheus
            object_data: Kubernetes object metadata
            
        Returns:
            Resource recommendations for CPU and Memory
        """
        try:
            # Extract comprehensive statistics from metrics
            stats = ai_prompts.extract_comprehensive_stats(history_data, object_data)
            
            # Check if we have enough data points
            total_points = stats.get("temporal", {}).get("total_data_points", 0)
            if total_points < self.settings.points_required:
                return {
                    ResourceType.CPU: ResourceRecommendation.undefined(info="Not enough data"),
                    ResourceType.Memory: ResourceRecommendation.undefined(info="Not enough data"),
                }
            
            # Check HPA if not allowed
            if object_data.hpa is not None and not self.settings.allow_hpa:
                if object_data.hpa.target_cpu_utilization_percentage is not None:
                    cpu_rec = ResourceRecommendation.undefined(info="HPA detected")
                else:
                    cpu_rec = None
                
                if object_data.hpa.target_memory_utilization_percentage is not None:
                    memory_rec = ResourceRecommendation.undefined(info="HPA detected")
                else:
                    memory_rec = None
                
                if cpu_rec and memory_rec:
                    return {
                        ResourceType.CPU: cpu_rec,
                        ResourceType.Memory: memory_rec,
                    }
            
            # Format messages for AI provider
            messages = ai_prompts.format_messages(
                self.provider_name,
                stats,
                object_data,
                self.settings
            )
            
            # Call AI provider
            logger.debug(f"Calling {self.provider_name} for recommendations...")
            result = self.provider.analyze_metrics(
                messages,
                temperature=self.settings.ai_temperature,
                max_tokens=self.settings.ai_max_tokens
            )
            
            # Parse and validate recommendations
            cpu_request = result.get("cpu_request")
            cpu_limit = result.get("cpu_limit")
            memory_request = result.get("memory_request")
            memory_limit = result.get("memory_limit")
            reasoning = result.get("reasoning", "")
            confidence = result.get("confidence", 0)
            
            # Apply minimum constraints from global config
            cpu_min = global_settings.cpu_min_value / 1000  # Convert from millicores to cores
            memory_min = global_settings.memory_min_value * 1024 * 1024  # Convert from MB to bytes
            
            # Apply maximum constraints (16 cores, 64GB)
            cpu_max = 16.0
            memory_max = 68719476736  # 64GB in bytes
            
            # Validate and clamp CPU
            if cpu_request is not None:
                cpu_request = max(cpu_min, min(cpu_max, cpu_request))
            if cpu_limit is not None:
                cpu_limit = max(cpu_min, min(cpu_max, cpu_limit))
            
            # Validate and clamp Memory
            if memory_request is not None:
                memory_request = max(memory_min, min(memory_max, int(memory_request)))
            if memory_limit is not None:
                memory_limit = max(memory_min, min(memory_max, int(memory_limit)))
            
            # Create info string with reasoning and confidence
            info_text = f"AI: {reasoning[:50]}{'...' if len(reasoning) > 50 else ''} (conf: {confidence}%)"
            
            # Sanity check against Simple strategy (log warnings only)
            self._sanity_check(stats, cpu_request, memory_request, object_data)
            
            return {
                ResourceType.CPU: ResourceRecommendation(
                    request=cpu_request,
                    limit=cpu_limit,
                    info=info_text
                ),
                ResourceType.Memory: ResourceRecommendation(
                    request=memory_request,
                    limit=memory_limit,
                    info=info_text
                ),
            }
            
        except Exception as e:
            logger.error(f"AI strategy failed for {object_data}: {e}", exc_info=True)
            return {
                ResourceType.CPU: ResourceRecommendation.undefined(info="AI error"),
                ResourceType.Memory: ResourceRecommendation.undefined(info="AI error"),
            }
    
    def _sanity_check(
        self, 
        stats: dict, 
        cpu_request: Optional[float], 
        memory_request: Optional[float],
        object_data: K8sObjectData
    ) -> None:
        """Perform sanity check comparing AI recommendations with Simple strategy.
        
        Logs warnings if recommendations differ significantly from Simple strategy.
        
        Args:
            stats: Statistics dictionary
            cpu_request: AI CPU request recommendation
            memory_request: AI Memory request recommendation
            object_data: Kubernetes object data
        """
        try:
            # Calculate Simple strategy baseline
            cpu_stats = stats.get("cpu", {})
            memory_stats = stats.get("memory", {})
            
            if cpu_request and cpu_stats:
                simple_cpu = cpu_stats.get("percentiles", {}).get("p95", 0)
                if simple_cpu > 0:
                    cpu_diff_pct = abs(cpu_request - simple_cpu) / simple_cpu * 100
                    if cpu_diff_pct > 500:  # More than 5x difference
                        logger.warning(
                            f"{object_data}: AI CPU recommendation ({cpu_request:.3f} cores) "
                            f"differs significantly from Simple strategy ({simple_cpu:.3f} cores, "
                            f"p95) - {cpu_diff_pct:.0f}% difference"
                        )
            
            if memory_request and memory_stats:
                simple_memory = memory_stats.get("max", 0) * (1 + self.settings.memory_buffer_percentage / 100)
                if simple_memory > 0:
                    memory_diff_pct = abs(memory_request - simple_memory) / simple_memory * 100
                    if memory_diff_pct > 300:  # More than 3x difference
                        logger.warning(
                            f"{object_data}: AI Memory recommendation ({memory_request / 1024**2:.0f} Mi) "
                            f"differs significantly from Simple strategy ({simple_memory / 1024**2:.0f} Mi) "
                            f"- {memory_diff_pct:.0f}% difference"
                        )
        
        except Exception as e:
            logger.debug(f"Sanity check failed: {e}")
