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
import time
from pathlib import Path
from typing import Any

import httpx


class GitHubAPIError(Exception):
    """Exception raised when GitHub API requests fail."""

    pass


class GitHubClient:
    """
    GitHub API client with pagination, rate limiting, and caching support.
    """

    def __init__(
        self,
        token: str | None = None,
        per_page: int = 100,
        max_retries: int = 3,
        cache_dir: Path | None = None,
    ):
        """
        Initialize GitHub API client.

        Args:
            token: GitHub Personal Access Token (None for unauthenticated requests)
            per_page: Number of items per page (1-100)
            max_retries: Maximum number of retries for failed requests
            cache_dir: Directory to cache raw API responses (None to disable caching)
        """
        self.base_url = "https://api.github.com"
        self.token = token
        self.per_page = min(max(per_page, 1), 100)
        self.max_retries = max_retries
        self.cache_dir = cache_dir

        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Setup headers
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

        self.client = httpx.Client(headers=self.headers, timeout=30.0, follow_redirects=True)

    def __enter__(self) -> "GitHubClient":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def _cache_response(self, cache_key: str, data: Any) -> None:
        """Cache API response to disk."""
        if not self.cache_dir:
            return

        cache_file = self.cache_dir / f"{cache_key}.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        retry_count: int = 0,
    ) -> dict[str, Any] | list[Any]:
        """
        Make a request to the GitHub API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/repos/owner/repo/issues")
            params: Query parameters
            retry_count: Current retry attempt number

        Returns:
            JSON response data

        Raises:
            GitHubAPIError: If request fails after all retries
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.client.request(method, url, params=params)

            # Handle rate limiting with exponential backoff
            if response.status_code == 403 and "rate limit" in response.text.lower():
                if retry_count < self.max_retries:
                    retry_after = int(response.headers.get("Retry-After", "60"))
                    wait_time = min(retry_after, 2 ** (retry_count + 1))
                    time.sleep(wait_time)
                    return self._request(method, endpoint, params, retry_count + 1)
                raise GitHubAPIError("Rate limit exceeded and max retries reached")

            # Handle other errors with exponential backoff
            if response.status_code >= 500:
                if retry_count < self.max_retries:
                    wait_time = 2 ** (retry_count + 1)
                    time.sleep(wait_time)
                    return self._request(method, endpoint, params, retry_count + 1)
                raise GitHubAPIError(
                    f"Server error {response.status_code} after {self.max_retries} retries"
                )

            # Handle 410 Gone (deleted content) gracefully
            if response.status_code == 410:
                return {}

            # Raise for other client errors
            if response.status_code >= 400:
                try:
                    error_data = response.json() if response.text else {}
                    message = error_data.get("message", response.text)
                except (json.JSONDecodeError, ValueError):
                    message = response.text or f"HTTP {response.status_code}"
                raise GitHubAPIError(f"GitHub API error {response.status_code}: {message}")

            response.raise_for_status()
            json_response: dict[str, Any] | list[Any] = response.json()
            return json_response

        except httpx.RequestError as e:
            if retry_count < self.max_retries:
                wait_time = 2 ** (retry_count + 1)
                time.sleep(wait_time)
                return self._request(method, endpoint, params, retry_count + 1)
            raise GitHubAPIError(f"Request failed after {self.max_retries} retries: {e}") from e

    def _paginate(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Paginate through all pages of a GitHub API endpoint.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            List of all items from all pages
        """
        params = params or {}
        params["per_page"] = self.per_page
        params["page"] = 1

        all_items: list[dict[str, Any]] = []

        while True:
            response = self._request("GET", endpoint, params)

            if isinstance(response, list):
                items = response
            elif isinstance(response, dict):
                items = response.get("items", [response])
            else:
                break

            if not items:
                break

            all_items.extend(items)

            # Check if there are more pages
            if len(items) < self.per_page:
                break

            params["page"] += 1

        return all_items

    def fetch_issues(self, owner: str, repo: str, state: str = "open") -> list[dict[str, Any]]:
        """
        Fetch all issues from a repository.

        Args:
            owner: Repository owner
            repo: Repository name
            state: Issue state filter (open, closed, all)

        Returns:
            List of issue data dictionaries
        """
        endpoint = f"/repos/{owner}/{repo}/issues"
        params = {"state": state, "sort": "created", "direction": "asc"}

        issues = self._paginate(endpoint, params)

        # Cache the raw response
        if self.cache_dir:
            self._cache_response(f"{owner}_{repo}_issues_{state}", issues)

        # Filter out pull requests (they appear in the issues endpoint)
        return [issue for issue in issues if "pull_request" not in issue]

    def fetch_issue_comments(
        self, owner: str, repo: str, issue_number: int
    ) -> list[dict[str, Any]]:
        """
        Fetch all comments for a specific issue.

        Args:
            owner: Repository owner
            repo: Repository name
            issue_number: Issue number

        Returns:
            List of comment data dictionaries
        """
        endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
        params = {"sort": "created", "direction": "asc"}

        comments = self._paginate(endpoint, params)

        # Cache the raw response
        if self.cache_dir:
            self._cache_response(f"{owner}_{repo}_issue_{issue_number}_comments", comments)

        return comments

    def check_repository_access(self, owner: str, repo: str) -> bool:
        """
        Check if the client has access to the repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            True if repository is accessible, False otherwise

        Raises:
            GitHubAPIError: If access check fails with an error other than 404
        """
        endpoint = f"/repos/{owner}/{repo}"

        try:
            self._request("GET", endpoint)
            return True
        except GitHubAPIError as e:
            if "404" in str(e):
                return False
            raise
