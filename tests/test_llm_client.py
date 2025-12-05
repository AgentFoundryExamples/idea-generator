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
Tests for the Ollama LLM client.
"""

import json

import httpx
import pytest

from idea_generator.llm.client import OllamaClient, OllamaError


class MockTransport(httpx.HTTPTransport):
    """Mock HTTP transport for testing without real API calls."""

    def __init__(self, responses: dict[str, dict]) -> None:
        """
        Initialize mock transport.

        Args:
            responses: Dictionary mapping endpoint paths to response data
        """
        super().__init__()
        self.responses = responses
        self.requests_made: list[tuple[str, dict]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle a mocked HTTP request."""
        path = request.url.path
        
        # Only try to parse JSON for requests with content
        if request.content:
            try:
                self.requests_made.append((path, json.loads(request.content)))
            except json.JSONDecodeError:
                self.requests_made.append((path, {}))
        else:
            self.requests_made.append((path, {}))

        if path in self.responses:
            response_data = self.responses[path]
            return httpx.Response(
                status_code=response_data.get("status", 200),
                json=response_data.get("json"),
                headers=response_data.get("headers", {}),
            )

        return httpx.Response(status_code=404, text="Not found")


class TestOllamaClient:
    """Tests for OllamaClient initialization and basic operations."""

    def test_client_initialization(self) -> None:
        """Test that client initializes with default values."""
        client = OllamaClient()
        assert client.base_url == "http://localhost:11434"
        assert client.timeout == 120.0
        assert client.max_retries == 3
        assert client.retry_delay == 1.0
        client.close()

    def test_client_custom_values(self) -> None:
        """Test that client accepts custom configuration."""
        client = OllamaClient(
            base_url="http://custom:8080",
            timeout=60.0,
            max_retries=5,
            retry_delay=2.0,
        )
        assert client.base_url == "http://custom:8080"
        assert client.timeout == 60.0
        assert client.max_retries == 5
        assert client.retry_delay == 2.0
        client.close()

    def test_client_context_manager(self) -> None:
        """Test that client works as a context manager."""
        with OllamaClient() as client:
            assert client.client is not None
        # Client should be closed after context

    def test_base_url_trailing_slash_stripped(self) -> None:
        """Test that trailing slash is removed from base URL."""
        client = OllamaClient(base_url="http://localhost:11434/")
        assert client.base_url == "http://localhost:11434"
        client.close()


class TestOllamaGenerate:
    """Tests for the generate() method."""

    def test_generate_success(self) -> None:
        """Test successful generation with JSON response."""
        mock_response = {
            "model": "llama3.2:latest",
            "response": '{"title": "Test", "summary": "A test summary"}',
            "done": True,
        }

        transport = MockTransport({"/api/generate": {"json": mock_response}})
        client = OllamaClient(transport=transport)

        result = client.generate(
            model="llama3.2:latest",
            prompt="Test prompt",
            system="Test system prompt",
        )

        assert result == mock_response
        assert len(transport.requests_made) == 1

        # Verify request payload
        _, payload = transport.requests_made[0]
        assert payload["model"] == "llama3.2:latest"
        assert payload["prompt"] == "Test prompt"
        assert payload["system"] == "Test system prompt"
        assert payload["stream"] is False
        assert payload["format"] == "json"

        client.close()

    def test_generate_without_system_prompt(self) -> None:
        """Test generation without system prompt."""
        mock_response = {"model": "llama3.2:latest", "response": "{}", "done": True}

        transport = MockTransport({"/api/generate": {"json": mock_response}})
        client = OllamaClient(transport=transport)

        client.generate(model="llama3.2:latest", prompt="Test")

        _, payload = transport.requests_made[0]
        assert "system" not in payload

        client.close()

    def test_generate_custom_temperature(self) -> None:
        """Test generation with custom temperature."""
        mock_response = {"model": "llama3.2:latest", "response": "{}", "done": True}

        transport = MockTransport({"/api/generate": {"json": mock_response}})
        client = OllamaClient(transport=transport)

        client.generate(model="llama3.2:latest", prompt="Test", temperature=0.3)

        _, payload = transport.requests_made[0]
        assert payload["temperature"] == 0.3

        client.close()

    def test_generate_http_error_client(self) -> None:
        """Test that client errors (4xx) don't retry."""
        transport = MockTransport({"/api/generate": {"status": 400, "json": {}}})
        client = OllamaClient(transport=transport, max_retries=3)

        with pytest.raises(OllamaError, match="HTTP 400"):
            client.generate(model="llama3.2:latest", prompt="Test")

        # Should not retry on client errors
        assert len(transport.requests_made) == 1

        client.close()

    def test_generate_http_error_server_retries(self) -> None:
        """Test that server errors (5xx) trigger retries."""
        # First two attempts fail, third succeeds
        call_count = 0

        def get_response() -> dict:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return {"status": 500, "json": {}}
            return {
                "status": 200,
                "json": {"model": "llama3.2:latest", "response": "{}", "done": True},
            }

        # We need to create a custom transport that changes behavior per call
        class RetryTransport(httpx.HTTPTransport):
            def __init__(self) -> None:
                super().__init__()
                self.call_count = 0

            def handle_request(self, request: httpx.Request) -> httpx.Response:
                self.call_count += 1
                if self.call_count < 3:
                    return httpx.Response(status_code=500, text="Server error")
                return httpx.Response(
                    status_code=200,
                    json={"model": "llama3.2:latest", "response": "{}", "done": True},
                )

        transport = RetryTransport()
        client = OllamaClient(transport=transport, max_retries=3, retry_delay=0.01)

        result = client.generate(model="llama3.2:latest", prompt="Test")

        assert result["done"] is True
        assert transport.call_count == 3

        client.close()

    def test_generate_timeout_retries(self) -> None:
        """Test that timeout errors trigger retries."""

        class TimeoutTransport(httpx.HTTPTransport):
            def __init__(self) -> None:
                super().__init__()
                self.call_count = 0

            def handle_request(self, request: httpx.Request) -> httpx.Response:
                self.call_count += 1
                if self.call_count < 3:
                    raise httpx.TimeoutException("Request timeout")
                return httpx.Response(
                    status_code=200,
                    json={"model": "llama3.2:latest", "response": "{}", "done": True},
                )

        transport = TimeoutTransport()
        client = OllamaClient(transport=transport, max_retries=3, retry_delay=0.01)

        result = client.generate(model="llama3.2:latest", prompt="Test")

        assert result["done"] is True
        assert transport.call_count == 3

        client.close()

    def test_generate_all_retries_exhausted(self) -> None:
        """Test that OllamaError is raised when all retries are exhausted."""

        class AlwaysFailTransport(httpx.HTTPTransport):
            def __init__(self) -> None:
                super().__init__()
                self.call_count = 0

            def handle_request(self, request: httpx.Request) -> httpx.Response:
                self.call_count += 1
                return httpx.Response(status_code=500, text="Server error")

        transport = AlwaysFailTransport()
        client = OllamaClient(transport=transport, max_retries=3, retry_delay=0.01)

        with pytest.raises(OllamaError, match="failed after 3 retries"):
            client.generate(model="llama3.2:latest", prompt="Test")

        assert transport.call_count == 3

        client.close()


class TestParseJSONResponse:
    """Tests for parse_json_response() method."""

    def test_parse_valid_json(self) -> None:
        """Test parsing valid JSON from response."""
        client = OllamaClient()
        response = {"response": '{"title": "Test", "value": 42}'}

        result = client.parse_json_response(response)

        assert result == {"title": "Test", "value": 42}
        client.close()

    def test_parse_json_with_whitespace(self) -> None:
        """Test parsing JSON with leading/trailing whitespace."""
        client = OllamaClient()
        response = {"response": '  {"title": "Test"}  \n'}

        result = client.parse_json_response(response)

        assert result == {"title": "Test"}
        client.close()

    def test_parse_json_in_code_block(self) -> None:
        """Test extracting JSON from markdown code block."""
        client = OllamaClient()
        response = {"response": '```json\n{"title": "Test"}\n```'}

        result = client.parse_json_response(response)

        assert result == {"title": "Test"}
        client.close()

    def test_parse_json_in_code_block_no_language(self) -> None:
        """Test extracting JSON from code block without language specifier."""
        client = OllamaClient()
        response = {"response": '```\n{"title": "Test"}\n```'}

        result = client.parse_json_response(response)

        assert result == {"title": "Test"}
        client.close()

    def test_parse_json_embedded_in_text(self) -> None:
        """Test extracting JSON object from surrounding text."""
        client = OllamaClient()
        response = {"response": 'Here is the result: {"title": "Test"} - done'}

        result = client.parse_json_response(response)

        assert result == {"title": "Test"}
        client.close()

    def test_parse_missing_response_field(self) -> None:
        """Test error when response field is missing."""
        client = OllamaClient()
        response = {"model": "llama3.2:latest"}

        with pytest.raises(OllamaError, match="missing 'response' field"):
            client.parse_json_response(response)

        client.close()

    def test_parse_empty_response(self) -> None:
        """Test error when response is empty."""
        client = OllamaClient()
        response = {"response": ""}

        with pytest.raises(OllamaError, match="Empty response"):
            client.parse_json_response(response)

        client.close()

    def test_parse_invalid_json(self) -> None:
        """Test error when response contains invalid JSON."""
        client = OllamaClient()
        response = {"response": "This is not JSON at all"}

        with pytest.raises(OllamaError, match="Failed to parse JSON"):
            client.parse_json_response(response)

        client.close()


class TestCheckHealth:
    """Tests for check_health() method."""

    def test_health_check_success(self) -> None:
        """Test successful health check."""
        transport = MockTransport({"/api/tags": {"json": {"models": []}}})
        client = OllamaClient(transport=transport)

        assert client.check_health() is True

        client.close()

    def test_health_check_failure(self) -> None:
        """Test health check with server error."""
        transport = MockTransport({"/api/tags": {"status": 500, "json": {}}})
        client = OllamaClient(transport=transport)

        assert client.check_health() is False

        client.close()

    def test_health_check_network_error(self) -> None:
        """Test health check with network error."""

        class ErrorTransport(httpx.HTTPTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                raise httpx.ConnectError("Connection refused")

        transport = ErrorTransport()
        client = OllamaClient(transport=transport)

        assert client.check_health() is False

        client.close()
