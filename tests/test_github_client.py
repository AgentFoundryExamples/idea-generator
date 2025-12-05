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
Copyright 2025 John Brosnihan

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from idea_generator.github_client import GitHubAPIError, GitHubClient


class TestGitHubClient:
    """Test suite for GitHubClient."""

    def test_client_initialization(self) -> None:
        """Test GitHubClient initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            client = GitHubClient(
                token="test_token",
                per_page=50,
                max_retries=5,
                cache_dir=cache_dir,
            )
            assert client.token == "test_token"
            assert client.per_page == 50
            assert client.max_retries == 5
            assert client.cache_dir == cache_dir
            assert cache_dir.exists()
            client.close()

    def test_client_without_token(self) -> None:
        """Test GitHubClient without authentication token."""
        client = GitHubClient()
        assert client.token is None
        assert "Authorization" not in client.headers
        client.close()

    def test_client_context_manager(self) -> None:
        """Test GitHubClient as context manager."""
        with GitHubClient() as client:
            assert client is not None
        # Client should be closed after exiting context

    def test_per_page_bounds(self) -> None:
        """Test per_page parameter bounds."""
        client = GitHubClient(per_page=0)
        assert client.per_page == 1
        client.close()

        client = GitHubClient(per_page=200)
        assert client.per_page == 100
        client.close()

    def test_cache_response(self) -> None:
        """Test caching API responses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            client = GitHubClient(cache_dir=cache_dir)

            test_data = {"test": "data"}
            client._cache_response("test_key", test_data)

            cache_file = cache_dir / "test_key.json"
            assert cache_file.exists()

            with open(cache_file) as f:
                cached_data = json.load(f)
            assert cached_data == test_data
            client.close()

    def test_cache_disabled(self) -> None:
        """Test that caching is disabled when cache_dir is None."""
        client = GitHubClient(cache_dir=None)
        # Should not raise error
        client._cache_response("test_key", {"test": "data"})
        client.close()

    @patch("httpx.Client.request")
    def test_request_success(self, mock_request: MagicMock) -> None:
        """Test successful API request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"key": "value"}
        mock_request.return_value = mock_response

        client = GitHubClient()
        result = client._request("GET", "/test")
        assert result == {"key": "value"}
        client.close()

    @patch("httpx.Client.request")
    def test_request_rate_limit_retry(self, mock_request: MagicMock) -> None:
        """Test retry on rate limit."""
        # First call: rate limit
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 403
        rate_limit_response.text = "rate limit exceeded"
        rate_limit_response.headers = {"Retry-After": "1"}

        # Second call: success
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"key": "value"}

        mock_request.side_effect = [rate_limit_response, success_response]

        client = GitHubClient(max_retries=3)
        with patch("time.sleep"):  # Mock sleep to speed up test
            result = client._request("GET", "/test")
        assert result == {"key": "value"}
        assert mock_request.call_count == 2
        client.close()

    @patch("httpx.Client.request")
    def test_request_rate_limit_exhausted(self, mock_request: MagicMock) -> None:
        """Test rate limit exhaustion."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "rate limit exceeded"
        mock_response.headers = {"Retry-After": "1"}
        mock_request.return_value = mock_response

        client = GitHubClient(max_retries=2)
        with patch("time.sleep"):
            with pytest.raises(GitHubAPIError, match="Rate limit exceeded"):
                client._request("GET", "/test")
        client.close()

    @patch("httpx.Client.request")
    def test_request_410_gone(self, mock_request: MagicMock) -> None:
        """Test handling of 410 Gone status (deleted content)."""
        mock_response = MagicMock()
        mock_response.status_code = 410
        mock_request.return_value = mock_response

        client = GitHubClient()
        result = client._request("GET", "/test")
        assert result == {}
        client.close()

    @patch("httpx.Client.request")
    def test_request_client_error(self, mock_request: MagicMock) -> None:
        """Test handling of client errors."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not Found"}
        mock_response.text = '{"message": "Not Found"}'
        mock_request.return_value = mock_response

        client = GitHubClient()
        with pytest.raises(GitHubAPIError, match="404"):
            client._request("GET", "/test")
        client.close()

    @patch("httpx.Client.request")
    def test_request_server_error_retry(self, mock_request: MagicMock) -> None:
        """Test retry on server errors."""
        # First call: server error
        error_response = MagicMock()
        error_response.status_code = 500

        # Second call: success
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"key": "value"}

        mock_request.side_effect = [error_response, success_response]

        client = GitHubClient(max_retries=3)
        with patch("time.sleep"):
            result = client._request("GET", "/test")
        assert result == {"key": "value"}
        client.close()

    @patch("httpx.Client.request")
    def test_request_network_error_retry(self, mock_request: MagicMock) -> None:
        """Test retry on network errors."""
        mock_request.side_effect = [
            httpx.RequestError("Network error"),
            MagicMock(status_code=200, json=lambda: {"key": "value"}),
        ]

        client = GitHubClient(max_retries=3)
        with patch("time.sleep"):
            result = client._request("GET", "/test")
        assert result == {"key": "value"}
        client.close()

    @patch("httpx.Client.request")
    def test_paginate_single_page(self, mock_request: MagicMock) -> None:
        """Test pagination with single page."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1}, {"id": 2}]
        mock_request.return_value = mock_response

        client = GitHubClient(per_page=100)
        result = client._paginate("/test")
        assert len(result) == 2
        assert result[0]["id"] == 1
        client.close()

    @patch("httpx.Client.request")
    def test_paginate_multiple_pages(self, mock_request: MagicMock) -> None:
        """Test pagination with multiple pages."""
        # First page: 100 items
        page1_response = MagicMock()
        page1_response.status_code = 200
        page1_response.json.return_value = [{"id": i} for i in range(100)]

        # Second page: 50 items
        page2_response = MagicMock()
        page2_response.status_code = 200
        page2_response.json.return_value = [{"id": i} for i in range(100, 150)]

        mock_request.side_effect = [page1_response, page2_response]

        client = GitHubClient(per_page=100)
        result = client._paginate("/test")
        assert len(result) == 150
        client.close()

    @patch("httpx.Client.request")
    def test_fetch_issues(self, mock_request: MagicMock) -> None:
        """Test fetching issues."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 1, "number": 1, "title": "Issue 1"},
            {"id": 2, "number": 2, "title": "Issue 2", "pull_request": {}},  # Should be filtered
        ]
        mock_request.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            client = GitHubClient(cache_dir=Path(tmpdir))
            issues = client.fetch_issues("owner", "repo")
            assert len(issues) == 1  # PR should be filtered out
            assert issues[0]["id"] == 1
            client.close()

    @patch("httpx.Client.request")
    def test_fetch_issue_comments(self, mock_request: MagicMock) -> None:
        """Test fetching issue comments."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 101, "body": "Comment 1"},
            {"id": 102, "body": "Comment 2"},
        ]
        mock_request.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            client = GitHubClient(cache_dir=Path(tmpdir))
            comments = client.fetch_issue_comments("owner", "repo", 1)
            assert len(comments) == 2
            assert comments[0]["id"] == 101
            client.close()

    @patch("httpx.Client.request")
    def test_check_repository_access_success(self, mock_request: MagicMock) -> None:
        """Test successful repository access check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 123}
        mock_request.return_value = mock_response

        client = GitHubClient()
        assert client.check_repository_access("owner", "repo") is True
        client.close()

    @patch("httpx.Client.request")
    def test_check_repository_access_not_found(self, mock_request: MagicMock) -> None:
        """Test repository not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not Found"}
        mock_response.text = '{"message": "Not Found"}'
        mock_request.return_value = mock_response

        client = GitHubClient()
        assert client.check_repository_access("owner", "repo") is False
        client.close()

    @patch("httpx.Client.request")
    def test_check_repository_access_error(self, mock_request: MagicMock) -> None:
        """Test repository access check with non-404 error."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"message": "Forbidden"}
        mock_response.text = '{"message": "Forbidden"}'
        mock_request.return_value = mock_response

        client = GitHubClient()
        with pytest.raises(GitHubAPIError, match="403"):
            client.check_repository_access("owner", "repo")
        client.close()
