from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CredentialProfileCreate(BaseModel):
    account_id: str = Field(default="default")
    base_url: str = Field(default="https://api.ticktick.com")
    user_agent: str
    x_device: str
    timezone: str = Field(default="Asia/Ho_Chi_Minh")
    locale: str = Field(default="en_US")
    csrf_header: str | None = None
    cookie_header: str


class SyncTaskBean(BaseModel):
    update: list[dict[str, Any]] = Field(default_factory=list)
    delete: list[dict[str, Any]] = Field(default_factory=list)
    add: list[dict[str, Any]] = Field(default_factory=list)
    empty: bool = False


class TickTickDelta(BaseModel):
    checkPoint: int
    syncTaskBean: SyncTaskBean | None = None
    projectProfiles: list[dict[str, Any]] | None = None
    projectGroups: list[dict[str, Any]] | None = None


class PollSummary(BaseModel):
    account_id: str
    source_checkpoint: int
    response_checkpoint: int
    updates_count: int
    deletes_count: int
    projects_count: int | None
    groups_count: int | None
    state_updated: bool