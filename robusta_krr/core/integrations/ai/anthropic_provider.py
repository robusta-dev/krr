"""Anthropic Claude provider implementation."""

from typing import Union
from .base import AIProvider


class AnthropicProvider(AIProvider):
    """Anthropic Claude API provider."""
    
    def _get_endpoint(self) -> str:
        """Get Anthropic API endpoint."""
        return "https://api.anthropic.com/v1/messages"
    
    def _get_headers(self) -> dict:
        """Get headers with x-api-key authentication."""
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
    
    def _format_request_body(
        self, 
        messages: Union[list, str], 
        temperature: float, 
        max_tokens: int
    ) -> dict:
        """Format request body for Anthropic API.
        
        Anthropic separates system message from conversation messages.
        
        Args:
            messages: List of message dicts or string
            temperature: Temperature for response randomness
            max_tokens: Maximum tokens in response
            
        Returns:
            Request body dictionary
        """
        # Convert string to messages format if needed
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        
        # Extract system message if present
        system_message = None
        conversation_messages = []
        
        for msg in messages:
            if msg.get("role") == "system":
                system_message = msg["content"]
            else:
                conversation_messages.append(msg)
        
        body = {
            "model": self.model,
            "messages": conversation_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if system_message:
            body["system"] = system_message
        
        return body
    
    def _parse_response(self, response_json: dict) -> str:
        """Parse Anthropic API response.
        
        Args:
            response_json: JSON response from API
            
        Returns:
            Content text from the response
        """
        return response_json["content"][0]["text"]
