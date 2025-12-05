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

from datetime import datetime

from pydantic import BaseModel, Field


class NormalizedComment(BaseModel):
    """
    Normalized representation of a GitHub issue comment.
    """

    id: int = Field(description="GitHub comment ID")
    author: str | None = Field(description="Comment author username (None for deleted users)")
    body: str = Field(description="Comment body text (cleaned)")
    created_at: datetime = Field(description="Comment creation timestamp")
    reactions: dict[str, int] = Field(
        default_factory=dict,
        description="Reaction counts (e.g., '+1': 5, 'heart': 2)",
    )


class NormalizedIssue(BaseModel):
    """
    Normalized representation of a GitHub issue with comments.
    """

    id: int = Field(description="GitHub issue ID")
    number: int = Field(description="Issue number in the repository")
    title: str = Field(description="Issue title")
    body: str = Field(description="Issue body text (cleaned)")
    labels: list[str] = Field(default_factory=list, description="Issue labels")
    state: str = Field(description="Issue state (open, closed)")
    reactions: dict[str, int] = Field(
        default_factory=dict,
        description="Reaction counts on the issue",
    )
    comments: list[NormalizedComment] = Field(
        default_factory=list,
        description="Comments on the issue (ordered by creation time)",
    )
    url: str = Field(description="GitHub issue URL")
    created_at: datetime = Field(description="Issue creation timestamp")
    updated_at: datetime = Field(description="Issue last update timestamp")
    is_noise: bool = Field(
        default=False,
        description="Flag indicating if this issue is likely noise/spam",
    )
    noise_reason: str | None = Field(
        default=None,
        description="Reason why this issue was flagged as noise (if applicable)",
    )
    truncated: bool = Field(
        default=False,
        description="Flag indicating if text was truncated",
    )
    original_length: int = Field(
        default=0,
        description="Original combined length before truncation",
    )
