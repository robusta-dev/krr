"""AI integrations for resource recommendations."""

from .base import AIProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .anthropic_provider import AnthropicProvider
from .ollama_provider import OllamaProvider


def get_provider(provider_name: str, api_key: str, model: str, timeout: int = 60) -> AIProvider:
    """Factory function to get the appropriate AI provider instance.
    
    Args:
        provider_name: Name of the provider (openai, gemini, anthropic, ollama)
        api_key: API key for authentication
        model: Model name to use
        timeout: Request timeout in seconds
        
    Returns:
        AIProvider instance
        
    Raises:
        ValueError: If provider_name is not recognized
    """
    providers = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "anthropic": AnthropicProvider,
        "ollama": OllamaProvider,
    }
    
    provider_class = providers.get(provider_name.lower())
    if provider_class is None:
        raise ValueError(
            f"Unknown AI provider: {provider_name}. "
            f"Available providers: {', '.join(providers.keys())}"
        )
    
    return provider_class(api_key=api_key, model=model, timeout=timeout)


__all__ = ["AIProvider", "get_provider"]
