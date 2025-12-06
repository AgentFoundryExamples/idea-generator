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
            if response.status_code == 403:
                # Check if it's a rate limit error using headers
                rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
                is_rate_limited = (
                    rate_limit_remaining == "0" or "rate limit" in response.text.lower()
                )

                if is_rate_limited and retry_count < self.max_retries:
                    # Use Retry-After header if available, otherwise exponential backoff
                    retry_after_header = response.headers.get("Retry-After")
                    if retry_after_header:
                        try:
                            retry_after = int(retry_after_header)
                        except ValueError:
                            retry_after = 60
                    else:
                        retry_after = 60

                    wait_time = min(retry_after, 2 ** (retry_count + 1))
                    time.sleep(wait_time)
                    return self._request(method, endpoint, params, retry_count + 1)
                elif is_rate_limited:
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
        self, endpoint: str, params: dict[str, Any] | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Paginate through all pages of a GitHub API endpoint.

        Args:
            endpoint: API endpoint
            params: Query parameters
            limit: Maximum number of items to fetch (None for no limit)

        Returns:
            List of all items from all pages (up to limit if specified)
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

            # Stop early if limit is reached
            if limit is not None and len(all_items) >= limit:
                all_items = all_items[:limit]
                break

            # Check if there are more pages
            if len(items) < self.per_page:
                break

            params["page"] += 1

        return all_items

    def fetch_issues(
        self, owner: str, repo: str, state: str = "open", limit: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Fetch issues from a repository, sorted by most recently updated.

        Args:
            owner: Repository owner
            repo: Repository name
            state: Issue state filter (open, closed, all)
            limit: Maximum number of issues to return (None for no limit)

        Returns:
            List of issue data dictionaries, sorted by updated_at descending
        """
        endpoint = f"/repos/{owner}/{repo}/issues"
        # Sort by updated (most recent first) for recency preference
        params = {"state": state, "sort": "updated", "direction": "desc"}

        issues = self._paginate(endpoint, params, limit=limit)

        # Cache the raw response
        if self.cache_dir:
            cache_key = f"{owner}_{repo}_issues_{state}"
            if limit:
                cache_key += f"_limit{limit}"
            self._cache_response(cache_key, issues)

        # Filter out pull requests (they appear in the issues endpoint)
        filtered_issues = [issue for issue in issues if "pull_request" not in issue]

        # Apply deterministic tiebreaker for identical timestamps
        # Sort by (updated_at, issue_number) both descending
        # - updated_at: Most recently updated issues first
        # - issue_number: When timestamps match, higher numbers (newer issues) first
        # - Missing timestamps use epoch date to sort to end
        # Note: GitHub issue numbers increment sequentially, so higher numbers = newer issues
        filtered_issues.sort(
            key=lambda x: (
                x.get("updated_at", "1970-01-01T00:00:00Z"),
                x.get("number", 0),
            ),
            reverse=True,
        )

        return filtered_issues

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
