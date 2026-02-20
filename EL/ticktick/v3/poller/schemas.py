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


class TaskSyncPayload(BaseModel):
    id: str
    projectId: str | None = None
    sortOrder: int | None = None
    title: str | None = None
    content: str | None = None
    timeZone: str | None = None
    isFloating: bool | None = None
    isAllDay: bool | None = None
    reminder: str | None = None
    reminders: list[Any] = Field(default_factory=list)
    exDate: list[Any] = Field(default_factory=list)
    priority: int | None = None
    status: int | None = None
    items: list[Any] = Field(default_factory=list)
    progress: int | None = None
    modifiedTime: str | None = None
    etag: str | None = None
    deleted: int | None = None
    createdTime: str | None = None
    completedTime: str | None = None
    completedUserId: int | None = None
    creator: int | None = None
    tags: list[str] = Field(default_factory=list)
    columnId: str | None = None
    kind: str | None = None
    startDate: str | None = None
    dueDate: str | None = None
    repeatFlag: str | None = None
    repeatFirstDate: str | None = None
    parentId: str | None = None


class SyncTaskBean(BaseModel):
    update: list[TaskSyncPayload] = Field(default_factory=list)
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

class ImportCurlRequest(BaseModel):
    curl_text: str
    account_id: str = Field(default="default")


class PollControlRequest(BaseModel):
    account_id: str = Field(default="default")
    owner_id: str = Field(default="web")
    interval_seconds: int | None = Field(default=None, ge=5, le=3600)