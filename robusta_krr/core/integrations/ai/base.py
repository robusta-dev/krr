"""Base abstract class for AI providers."""

import abc
import json
import logging
import re
from typing import Union

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("krr")


class AIProvider(abc.ABC):
    """Abstract base class for AI providers.
    
    All AI providers must implement the abstract methods to handle
    provider-specific API details (endpoint, headers, request format, response parsing).
    
    The analyze_metrics method is concrete and handles the common logic:
    retry, HTTP requests, error handling, and JSON extraction.
    """
    
    def __init__(self, api_key: str, model: str, timeout: int = 60):
        """Initialize the AI provider.
        
        Args:
            api_key: API key for authentication
            model: Model name to use
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
    
    @abc.abstractmethod
    def _get_endpoint(self) -> str:
        """Get the API endpoint URL.
        
        Returns:
            API endpoint URL
        """
        pass
    
    @abc.abstractmethod
    def _get_headers(self) -> dict:
        """Get the HTTP headers for the request.
        
        Returns:
            Dictionary of HTTP headers
        """
        pass
    
    @abc.abstractmethod
    def _format_request_body(
        self, 
        messages: Union[list, str], 
        temperature: float, 
        max_tokens: int
    ) -> dict:
        """Format the request body for the provider's API.
        
        Args:
            messages: Messages to send (format depends on provider)
            temperature: Temperature for response randomness
            max_tokens: Maximum tokens in response
            
        Returns:
            Dictionary containing the request body
        """
        pass
    
    @abc.abstractmethod
    def _parse_response(self, response_json: dict) -> str:
        """Parse the response from the provider's API.
        
        Args:
            response_json: JSON response from the API
            
        Returns:
            Text content from the response
        """
        pass
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout))
    )
    def analyze_metrics(
        self, 
        messages: Union[list, str], 
        temperature: float = 0.3, 
        max_tokens: int = 2000
    ) -> dict:
        """Analyze metrics and get resource recommendations from the AI.
        
        This method handles the complete request/response cycle with retry logic.
        
        Args:
            messages: Messages to send to the AI
            temperature: Temperature for response randomness (0-2)
            max_tokens: Maximum tokens in response
            
        Returns:
            Dictionary with recommendation data
            
        Raises:
            requests.RequestException: If the request fails after retries
            ValueError: If response parsing fails
        """
        try:
            payload = self._format_request_body(messages, temperature, max_tokens)
            
            logger.info(
                f"Sending request to {self.__class__.__name__} "
                f"(model: {self.model}, temp: {temperature}, max_tokens: {max_tokens})"
            )
            
            response = requests.post(
                self._get_endpoint(),
                headers=self._get_headers(),
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            text = self._parse_response(response.json())
            result = self._extract_json(text)
            
            # Validate required fields are present and complete
            required_fields = ["cpu_request", "cpu_limit", "memory_request", "memory_limit", "reasoning", "confidence"]
            missing_fields = [field for field in required_fields if field not in result]
            if missing_fields:
                logger.error(
                    f"Response from {self.__class__.__name__} missing required fields: {missing_fields}. "
                    f"Response: {text[:500]}"
                )
                raise ValueError(
                    f"Incomplete JSON response from {self.__class__.__name__} - missing fields: {missing_fields}. "
                    f"Try increasing --ai-max-tokens or using --ai-compact-mode."
                )
            
            # Check for truncated reasoning field (common truncation indicator)
            reasoning = result.get("reasoning", "")
            if reasoning and reasoning.strip().endswith("..."):
                logger.warning(
                    f"Response from {self.__class__.__name__} appears truncated (reasoning ends with '...'). "
                    f"Consider increasing --ai-max-tokens."
                )
            
            logger.debug(f"Successfully received and validated response from {self.__class__.__name__}")
            
            return result
            
        except requests.HTTPError as e:
            logger.error(
                f"HTTP error from {self.__class__.__name__}: {e.response.status_code} - {e.response.text}"
            )
            raise
        except requests.Timeout as e:
            logger.error(f"Timeout calling {self.__class__.__name__} API after {self.timeout}s")
            raise
        except requests.RequestException as e:
            logger.error(f"Request error calling {self.__class__.__name__}: {e}")
            raise
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse response from {self.__class__.__name__}: {e}")
            raise ValueError(f"Invalid response format from {self.__class__.__name__}: {e}")
    
    def _extract_json(self, text: str) -> dict:
        """Extract JSON from text, handling markdown code blocks.
        
        Args:
            text: Text that may contain JSON
            
        Returns:
            Parsed JSON as dictionary
            
        Raises:
            ValueError: If JSON cannot be extracted or parsed
        """
        # Try direct JSON parsing first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from markdown code blocks
        # Pattern matches ```json\n{...}\n``` or just {...}
        patterns = [
            r'```(?:json)?\s*(\{[^`]+\})\s*```',  # Markdown code block
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',   # Plain JSON object
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                json_str = match.group(1) if match.lastindex else match.group(0)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
        
        # Check if response looks truncated
        is_truncated = not text.strip().endswith('}')
        truncation_hint = " (Response appears truncated - increase --ai-max-tokens)" if is_truncated else ""
        
        raise ValueError(
            f"Could not extract valid JSON from response{truncation_hint}. "
            f"Response text: {text[:300]}..."
        )
