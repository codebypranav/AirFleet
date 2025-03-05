"""
Direct OpenAI API Access

This module provides direct access to OpenAI APIs using the requests library,
bypassing the OpenAI Python client entirely to avoid proxy issues.
"""
import os
import json
import logging
import requests
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DirectOpenAI:
    """
    Direct OpenAI API access using requests instead of the OpenAI client library.
    This bypasses any proxy-related issues with the OpenAI client.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the direct OpenAI client.
        
        Args:
            api_key: OpenAI API key. If None, will be read from OPENAI_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("No API key provided and OPENAI_API_KEY environment variable not set")
        
        self.base_url = "https://api.openai.com/v1"
        self.chat = ChatCompletions(self)
        
    def _request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a request to the OpenAI API.
        
        Args:
            method: HTTP method (get, post, etc.)
            endpoint: API endpoint (without the base URL)
            data: Request data
            
        Returns:
            Response data as dictionary
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"Making {method} request to {endpoint}")
            if method.lower() == "get":
                response = requests.get(url, headers=headers, params=data)
            elif method.lower() == "post":
                response = requests.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response text: {e.response.text}")
                try:
                    error_data = json.loads(e.response.text)
                    raise ValueError(f"OpenAI API error: {error_data.get('error', {}).get('message', str(e))}")
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"OpenAI API request failed: {str(e)}")


class ChatCompletions:
    """
    Direct access to the chat completions API.
    """
    
    def __init__(self, client: DirectOpenAI):
        """
        Initialize chat completions.
        
        Args:
            client: DirectOpenAI client
        """
        self.client = client
    
    def create(self, 
               model: str, 
               messages: List[Dict[str, str]], 
               max_tokens: Optional[int] = None,
               temperature: Optional[float] = None,
               top_p: Optional[float] = None) -> Dict[str, Any]:
        """
        Create a chat completion.
        
        Args:
            model: Model name
            messages: List of message dictionaries with 'role' and 'content'
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            
        Returns:
            Chat completion response
        """
        data = {
            "model": model,
            "messages": messages
        }
        
        if max_tokens is not None:
            data["max_tokens"] = max_tokens
        
        if temperature is not None:
            data["temperature"] = temperature
            
        if top_p is not None:
            data["top_p"] = top_p
            
        response = self.client._request("post", "chat/completions", data)
        
        # Format the response to match the structure expected by calling code
        try:
            # Create an object with dot-notation access mirroring the OpenAI library's response
            class ObjectWithDotNotation:
                def __init__(self, data):
                    for key, value in data.items():
                        if isinstance(value, dict):
                            value = ObjectWithDotNotation(value)
                        elif isinstance(value, list):
                            value = [ObjectWithDotNotation(item) if isinstance(item, dict) else item for item in value]
                        setattr(self, key, value)
            
            # Restructure the choices to match the OpenAI library's response structure
            for choice in response.get("choices", []):
                if "message" in choice:
                    # Make sure message has content accessible through dot notation
                    choice["message"] = ObjectWithDotNotation(choice["message"])
            
            return ObjectWithDotNotation(response)
        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}")
            # If formatting fails, return the raw response
            return response


def create_direct_client(api_key: Optional[str] = None) -> DirectOpenAI:
    """
    Create a direct OpenAI client that bypasses the official library.
    
    Args:
        api_key: OpenAI API key. If None, will be read from OPENAI_API_KEY environment variable.
        
    Returns:
        DirectOpenAI client
    """
    try:
        logger.info("Creating direct OpenAI client")
        return DirectOpenAI(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to create direct OpenAI client: {str(e)}")
        raise 