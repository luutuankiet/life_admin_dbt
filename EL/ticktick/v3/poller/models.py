from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """Attach UTC to a naive datetime coming back from SQLite, or passthrough if already tz-aware."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def make_pk(account_id: str, source_id: str) -> str:
    return f"{account_id}:{source_id}"


class CredentialProfile(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    account_id: str = Field(index=True)
    is_active: bool = Field(default=True)

    base_url: str = Field(default="https://api.ticktick.com")
    user_agent: str
    x_device: str
    timezone: str = Field(default="Asia/Ho_Chi_Minh")
    locale: str = Field(default="en_US")
    csrf_header: str | None = None
    cookie_header: str

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class PollerLease(SQLModel, table=True):
    account_id: str = Field(primary_key=True)
    owner_id: str
    lease_until: datetime
    heartbeat_at: datetime = Field(default_factory=utcnow)


class CheckpointState(SQLModel, table=True):
    account_id: str = Field(primary_key=True)
    checkpoint: int = Field(default=0)
    last_status: str = Field(default="never_run")
    last_error: str | None = None
    error_streak: int = Field(default=0)
    updated_at: datetime = Field(default_factory=utcnow)
    last_success_at: datetime | None = None


class TaskReplica(SQLModel, table=True):
    pk: str = Field(primary_key=True)
    account_id: str = Field(index=True)
    task_id: str = Field(index=True)

    project_id: str | None = None
    title: str | None = None
    content: str | None = None
    status: int | None = None
    deleted: int | None = None
    etag: str | None = None
    modified_time: str | None = None
    created_time: str | None = None
    completed_time: str | None = None
    completed_user_id: int | None = None
    column_id: str | None = None
    kind: str | None = None

    raw_json: str
    updated_at: datetime = Field(default_factory=utcnow)


class ProjectReplica(SQLModel, table=True):
    pk: str = Field(primary_key=True)
    account_id: str = Field(index=True)
    project_id: str = Field(index=True)

    name: str | None = None
    group_id: str | None = None
    closed: bool | None = None
    sort_order: int | None = None
    etag: str | None = None
    modified_time: str | None = None
    kind: str | None = None
    view_mode: str | None = None

    raw_json: str
    updated_at: datetime = Field(default_factory=utcnow)


class GroupReplica(SQLModel, table=True):
    pk: str = Field(primary_key=True)
    account_id: str = Field(index=True)
    group_id: str = Field(index=True)

    name: str | None = None
    deleted: int | None = None
    sort_order: int | None = None
    etag: str | None = None
    sort_type: str | None = None
    sort_option_json: str | None = None

    raw_json: str
    updated_at: datetime = Field(default_factory=utcnow)


class PollCycle(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    account_id: str = Field(index=True)
    owner_id: str

    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    status: str = Field(default="running")
    source_checkpoint: int = Field(default=0)
    response_checkpoint: int | None = None
    updates_count: int = Field(default=0)
    deletes_count: int = Field(default=0)
    projects_count: int | None = None
    groups_count: int | None = None
    error_message: str | None = None