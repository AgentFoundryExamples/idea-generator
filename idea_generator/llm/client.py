# Copyright 2025 John Brosnihan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Ollama HTTP client for interacting with local LLM instances.

This module provides a wrapper around the Ollama API with support for:
- Configurable endpoints and timeouts
- Retry logic with exponential backoff
- Dependency injection for testing (mock transports)
- JSON response parsing and validation
"""

import json
import time
from typing import Any

import httpx


class OllamaError(Exception):
    """Base exception for Ollama client errors."""

    pass


class OllamaClient:
    """
    HTTP client for interacting with Ollama API.

    This client is designed for 3-8B parameter models with appropriate
    timeouts and retry logic. It supports dependency injection for testing
    without calling real models.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        timeout: float = 120.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        transport: httpx.HTTPTransport | None = None,
    ) -> None:
        """
        Initialize Ollama client.

        Args:
            base_url: Ollama server base URL (default: http://localhost:11434)
            timeout: Request timeout in seconds (default: 120s for 3-8B models)
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Initial delay between retries in seconds (default: 1.0)
            transport: Optional HTTP transport for dependency injection (testing)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Create HTTP client with optional transport injection
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            transport=transport,
        )

    def __enter__(self) -> "OllamaClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit - close HTTP client."""
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        format: str | None = "json",
    ) -> dict[str, Any]:
        """
        Generate a completion from the Ollama model.

        Args:
            model: Name of the Ollama model to use
            prompt: The prompt to send to the model
            system: Optional system prompt to set model behavior
            temperature: Sampling temperature (0.0-1.0, default: 0.7)
            format: Response format, "json" for JSON mode (default: "json")

        Returns:
            Dictionary containing the response with keys:
            - response: The generated text
            - model: The model used
            - done: Whether generation is complete

        Raises:
            OllamaError: If the request fails after retries or returns invalid JSON
        """
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "temperature": temperature,
            "stream": False,
        }

        if system:
            payload["system"] = system

        if format:
            payload["format"] = format

        # Retry loop with exponential backoff
        last_exception: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.post("/api/generate", json=payload)
                response.raise_for_status()

                result: dict[str, Any] = response.json()
                return result

            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code >= 500:
                    # Server error - retry with backoff
                    if attempt < self.max_retries - 1:
                        delay = self.retry_delay * (2**attempt)
                        time.sleep(delay)
                        continue
                    # Last retry exhausted for server error
                    break
                # Client error - don't retry
                raise OllamaError(f"HTTP {e.response.status_code}: {e.response.text}") from e

            except httpx.TimeoutException as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    time.sleep(delay)
                    continue
                # Last retry exhausted
                break

            except httpx.RequestError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    time.sleep(delay)
                    continue
                # Last retry exhausted
                break

            except json.JSONDecodeError as e:
                # JSON parsing error - don't retry
                raise OllamaError(f"Invalid JSON response: {e}") from e

        # All retries exhausted
        raise OllamaError(f"Request failed after {self.max_retries} retries: {last_exception}")

    def parse_json_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """
        Parse and validate JSON from the model response.

        Args:
            response: The raw response from generate()

        Returns:
            Parsed JSON object from the response text

        Raises:
            OllamaError: If response doesn't contain valid JSON
        """
        if "response" not in response:
            raise OllamaError("Response missing 'response' field")

        response_text = response["response"]
        if not response_text:
            raise OllamaError("Empty response from model")

        try:
            # Try to parse as JSON
            parsed: dict[str, Any] = json.loads(response_text)
            return parsed
        except json.JSONDecodeError as e:
            # Try to extract JSON from markdown code blocks
            import re

            # Look for JSON in code blocks: ```json ... ```
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
            if json_match:
                try:
                    parsed_from_block: dict[str, Any] = json.loads(json_match.group(1))
                    return parsed_from_block
                except json.JSONDecodeError:
                    pass

            # Look for raw JSON object
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                try:
                    parsed_raw: dict[str, Any] = json.loads(json_match.group(0))
                    return parsed_raw
                except json.JSONDecodeError:
                    pass

            raise OllamaError(f"Failed to parse JSON from response: {e}") from e

    def check_health(self) -> bool:
        """
        Check if the Ollama server is accessible.

        Returns:
            True if server is healthy, False otherwise
        """
        try:
            response = self.client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False
