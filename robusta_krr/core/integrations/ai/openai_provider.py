"""OpenAI provider implementation."""

from typing import Union
from .base import AIProvider


class OpenAIProvider(AIProvider):
    """OpenAI API provider (GPT models)."""
    
    def _get_endpoint(self) -> str:
        """Get OpenAI API endpoint."""
        return "https://api.openai.com/v1/chat/completions"
    
    def _get_headers(self) -> dict:
        """Get headers with Bearer token authentication."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _format_request_body(
        self, 
        messages: Union[list, str], 
        temperature: float, 
        max_tokens: int
    ) -> dict:
        """Format request body for OpenAI API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Temperature for response randomness
            max_tokens: Maximum tokens in response
            
        Returns:
            Request body dictionary
        """
        # Convert string to messages format if needed
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        
        return {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"}  # Force JSON output
        }
    
    def _parse_response(self, response_json: dict) -> str:
        """Parse OpenAI API response.
        
        Args:
            response_json: JSON response from API
            
        Returns:
            Content text from the response
        """
        return response_json["choices"][0]["message"]["content"]
