"""Google Gemini provider implementation."""

from typing import Union
from .base import AIProvider


class GeminiProvider(AIProvider):
    """Google Gemini API provider."""
    
    def _get_endpoint(self) -> str:
        """Get Gemini API endpoint with API key in URL."""
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
    
    def _get_headers(self) -> dict:
        """Get headers for Gemini API."""
        return {
            "Content-Type": "application/json"
        }
    
    def _format_request_body(
        self, 
        messages: Union[list, str], 
        temperature: float, 
        max_tokens: int
    ) -> dict:
        """Format request body for Gemini API.
        
        Gemini uses a different format than OpenAI - it expects 'contents'
        with 'parts' containing text.
        
        Args:
            messages: Messages (list or string)
            temperature: Temperature for response randomness
            max_tokens: Maximum tokens in response
            
        Returns:
            Request body dictionary
        """
        # Convert messages to Gemini format
        if isinstance(messages, str):
            text = messages
        elif isinstance(messages, list):
            # Concatenate all messages into single text
            text = "\n\n".join(
                f"{msg.get('role', 'user').upper()}: {msg['content']}"
                for msg in messages
            )
        else:
            text = str(messages)
        
        # Add explicit instructions for complete JSON output with validation
        text += "\n\n⚠️ CRITICAL: You MUST respond with COMPLETE, VALID JSON only."
        text += "\nBefore responding, verify:"
        text += "\n1. JSON starts with {{ and ends with }}"
        text += "\n2. All 6 required fields are present: cpu_request, cpu_limit, memory_request, memory_limit, reasoning, confidence"
        text += "\n3. All braces and quotes are properly closed"
        text += "\n4. Response is parseable JSON"
        text += "\nDo NOT send incomplete or truncated JSON."
        
        return {
            "contents": [
                {
                    "parts": [
                        {"text": text}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json"
            }
        }
    
    def _parse_response(self, response_json: dict) -> str:
        """Parse Gemini API response.
        
        Args:
            response_json: JSON response from API
            
        Returns:
            Content text from the response
        """
        return response_json["candidates"][0]["content"]["parts"][0]["text"]
