import json
import re
import time
import logging
import httpx
from typing import Any, Dict
from sqlalchemy.orm import Session
from src.config.config import get_env
from src.utils.decorators import try_except_decorator_no_raise, retry_on_429


class ChatGPTService:
    def __init__(self, db: Session):
        # db not used, kept for DI compatibility
        self.db = db
        self.api_key: str = get_env("OPENAI_API_KEY", required=True)
        self.model: str = get_env("OPENAI_MODEL", default="gpt-4o")

    @retry_on_429(max_retries=3, initial_wait=1)
    def generate_response(self, prompt: str, **kwargs) -> str:
        """
        Generate a response from ChatGPT.
        
        If the API returns a 429 status code (rate limit), wait for 1 minute and retry.
        For other errors, return an empty string.
        
        Args:
            prompt: The prompt to send to ChatGPT
            **kwargs: Additional arguments to pass to the API
            
        Returns:
            The generated response, or an empty string if an error occurs
        """
        if not isinstance(prompt, str) or not prompt.strip():
            logging.error("ChatGPT prompt must be a non-empty string")
            return ''

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }
        
        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            
            response.raise_for_status()
            
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
            
        except httpx.HTTPStatusError as e:
            # Let the decorator handle 429s, catch others
            if e.response.status_code == 429:
                raise # Re-raise for decorator
            logging.error(f"HTTP error in ChatGPT API: {e.response.status_code} - {e.response.text}")
            return ''
        except Exception as e:
            logging.error(f"Error in ChatGPT API: {str(e)}")
            return ''

    @staticmethod
    def parse_gpt_json(raw: str) -> Dict[str, Any]:
        """
        Extract and decode the first JSON object from a ChatGPT reply.

        Handles
        -------
        • Removes code-fence markers  ``` and ```json (or any language tag).  
        • Ignores any prose before/after the JSON block.  
        • Robust to nested braces and braces inside strings (delegates to the
        standard JSON decoder).

        Returns
        -------
        dict
            Parsed JSON as a Python dict.

        Raises
        ------
        ValueError
            If no JSON is found, the JSON is malformed, or the top-level JSON
            value is not an object.
        """
        _CODE_FENCE_RE = re.compile(r"```(?:\w+)?\n?|```")
        _JSON_DECODER = json.JSONDecoder()

        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("raw must be a non-empty string")

        # 1) Strip code fences in one go                                    
        cleaned: str = _CODE_FENCE_RE.sub("", raw).strip()

        # 2) Locate the first opening brace                                 
        start: int = cleaned.find("{")
        if start == -1:
            raise ValueError("No opening '{' found in response")

        # 3) Let the built-in JSON decoder grab exactly one JSON value      
        try:
            obj, _ = _JSON_DECODER.raw_decode(cleaned[start:])
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON: {e.msg}") from e

        # 4) Ensure the top-level value is a JSON object (dict)             
        if not isinstance(obj, dict):
            raise ValueError("Top-level JSON value is not an object")

        return obj
