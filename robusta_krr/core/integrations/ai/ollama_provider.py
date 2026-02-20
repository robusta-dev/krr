"""Ollama local provider implementation."""

import os
from typing import Union
from .base import AIProvider


class OllamaProvider(AIProvider):
    """Ollama local API provider for running models locally."""
    
    def __init__(self, api_key: str, model: str, timeout: int = 60):
        """Initialize Ollama provider.
        
        Args:
            api_key: Not used for Ollama, but kept for interface consistency
            model: Model name to use
            timeout: Request timeout in seconds
        """
        super().__init__(api_key, model, timeout)
        # Get Ollama host from environment or use default
        self.host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    
    def _get_endpoint(self) -> str:
        """Get Ollama API endpoint."""
        return f"{self.host}/api/generate"
    
    def _get_headers(self) -> dict:
        """Get headers for Ollama API (no authentication needed)."""
        return {
            "Content-Type": "application/json"
        }
    
    def _format_request_body(
        self, 
        messages: Union[list, str], 
        temperature: float, 
        max_tokens: int
    ) -> dict:
        """Format request body for Ollama API.
        
        Ollama uses a simpler format with just a prompt.
        
        Args:
            messages: Messages (list or string)
            temperature: Temperature for response randomness
            max_tokens: Maximum tokens in response
            
        Returns:
            Request body dictionary
        """
        # Convert messages to single prompt string
        if isinstance(messages, str):
            prompt = messages
        elif isinstance(messages, list):
            # Concatenate all messages
            prompt = "\n\n".join(
                f"{msg.get('role', 'user').upper()}: {msg['content']}"
                for msg in messages
            )
        else:
            prompt = str(messages)
        
        # Add instruction for JSON output
        prompt += "\n\nIMPORTANT: Respond with valid JSON only, no additional text."
        
        return {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "format": "json"  # Request JSON format
        }
    
    def _parse_response(self, response_json: dict) -> str:
        """Parse Ollama API response.
        
        Args:
            response_json: JSON response from API
            
        Returns:
            Content text from the response
        """
        return response_json["response"]
