from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, delete, select

from .models import (
    CheckpointState,
    CredentialProfile,
    GroupReplica,
    PollCycle,
    PollerLease,
    ProjectReplica,
    TaskReplica,
    ensure_utc,
    make_pk,
)
from .schemas import CredentialProfileCreate


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReplicaRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_active_profile(self, profile_in: CredentialProfileCreate) -> CredentialProfile:
        active_profiles = self.session.exec(
            select(CredentialProfile).where(CredentialProfile.account_id == profile_in.account_id)
        ).all()
        for profile in active_profiles:
            profile.is_active = False
            profile.updated_at = utcnow()
            self.session.add(profile)

        profile = CredentialProfile(
            account_id=profile_in.account_id,
            is_active=True,
            base_url=profile_in.base_url,
            user_agent=profile_in.user_agent,
            x_device=profile_in.x_device,
            timezone=profile_in.timezone,
            locale=profile_in.locale,
            csrf_header=profile_in.csrf_header,
            cookie_header=profile_in.cookie_header,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        self.session.add(profile)

        state = self.get_or_create_checkpoint_state(profile_in.account_id)
        self.session.add(state)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def get_active_profile(self, account_id: str) -> CredentialProfile | None:
        return self.session.exec(
            select(CredentialProfile)
            .where(CredentialProfile.account_id == account_id)
            .where(CredentialProfile.is_active)
            .order_by(CredentialProfile.created_at.desc())
        ).first()

    def get_or_create_checkpoint_state(self, account_id: str) -> CheckpointState:
        state = self.session.get(CheckpointState, account_id)
        if state:
            return state
        state = CheckpointState(account_id=account_id)
        self.session.add(state)
        self.session.flush()
        return state

    def try_acquire_lease(self, account_id: str, owner_id: str, ttl_seconds: int) -> bool:
        now = utcnow()
        lease = self.session.get(PollerLease, account_id)
        if not lease:
            lease = PollerLease(
                account_id=account_id,
                owner_id=owner_id,
                lease_until=datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=timezone.utc),
                heartbeat_at=now,
            )
            self.session.add(lease)
            self.session.commit()
            return True

        if lease.owner_id == owner_id or ensure_utc(lease.lease_until) <= now:
            lease.owner_id = owner_id
            lease.heartbeat_at = now
            lease.lease_until = datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=timezone.utc)
            self.session.add(lease)
            self.session.commit()
            return True

        return False

    def heartbeat_lease(self, account_id: str, owner_id: str, ttl_seconds: int) -> None:
        lease = self.session.get(PollerLease, account_id)
        if not lease or lease.owner_id != owner_id:
            raise RuntimeError("Lease ownership lost.")
        now = utcnow()
        lease.heartbeat_at = now
        lease.lease_until = datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=timezone.utc)
        self.session.add(lease)
        self.session.commit()

    def start_cycle(self, account_id: str, owner_id: str, source_checkpoint: int) -> PollCycle:
        cycle = PollCycle(account_id=account_id, owner_id=owner_id, source_checkpoint=source_checkpoint)
        self.session.add(cycle)
        self.session.commit()
        self.session.refresh(cycle)
        return cycle

    def finish_cycle_success(
        self,
        cycle: PollCycle,
        response_checkpoint: int,
        updates_count: int,
        deletes_count: int,
        projects_count: int | None,
        groups_count: int | None,
    ) -> None:
        cycle.status = "success"
        cycle.finished_at = utcnow()
        cycle.response_checkpoint = response_checkpoint
        cycle.updates_count = updates_count
        cycle.deletes_count = deletes_count
        cycle.projects_count = projects_count
        cycle.groups_count = groups_count
        self.session.add(cycle)
        self.session.commit()

    def finish_cycle_error(self, cycle: PollCycle, error_message: str) -> None:
        cycle.status = "error"
        cycle.finished_at = utcnow()
        cycle.error_message = error_message
        self.session.add(cycle)
        self.session.commit()

    def upsert_task_patch(self, account_id: str, patch: Any) -> None:
        if hasattr(patch, "model_dump"):
            payload = patch.model_dump(exclude_unset=True)
        elif isinstance(patch, dict):
            payload = patch
        else:
            return

        task_id = payload.get("id")
        if not task_id:
            return

        pk = make_pk(account_id, task_id)
        row = self.session.get(TaskReplica, pk)

        if row is None:
            row = TaskReplica(pk=pk, account_id=account_id, task_id=task_id, raw_json="{}")

        row.project_id = payload.get("projectId")
        row.sort_order = payload.get("sortOrder")
        row.title = payload.get("title")
        row.content = payload.get("content")
        row.timezone = payload.get("timeZone")
        row.is_floating = payload.get("isFloating")
        row.is_all_day = payload.get("isAllDay")
        row.reminder = payload.get("reminder")
        row.priority = payload.get("priority")
        row.status = payload.get("status")
        row.deleted = payload.get("deleted")
        row.progress = payload.get("progress")
        row.etag = payload.get("etag")
        row.start_date = payload.get("startDate")
        row.due_date = payload.get("dueDate")
        row.repeat_flag = payload.get("repeatFlag")
        row.repeat_first_date = payload.get("repeatFirstDate")
        row.modified_time = payload.get("modifiedTime")
        row.created_time = payload.get("createdTime")
        row.completed_time = payload.get("completedTime")
        row.completed_user_id = payload.get("completedUserId")
        row.creator = payload.get("creator")
        row.parent_id = payload.get("parentId")
        row.column_id = payload.get("columnId")
        row.kind = payload.get("kind")
        row.raw_json = json.dumps(payload, ensure_ascii=False)
        row.updated_at = utcnow()

        self.session.add(row)

    def delete_tasks(self, account_id: str, deletions: list[dict]) -> int:
        task_ids = [item.get("taskId") or item.get("id") for item in deletions]
        task_ids = [task_id for task_id in task_ids if task_id]
        if not task_ids:
            return 0
        deleted_rows = 0
        for task_id in task_ids:
            pk = make_pk(account_id, task_id)
            row = self.session.get(TaskReplica, pk)
            if row:
                self.session.delete(row)
                deleted_rows += 1
        return deleted_rows

    def replace_projects(self, account_id: str, profiles: list[dict]) -> None:
        incoming = {item.get("id"): item for item in profiles if item.get("id")}
        existing = self.session.exec(
            select(ProjectReplica).where(ProjectReplica.account_id == account_id)
        ).all()

        for row in existing:
            if row.project_id not in incoming:
                self.session.delete(row)

        for project_id, payload in incoming.items():
            pk = make_pk(account_id, project_id)
            row = self.session.get(ProjectReplica, pk)
            if row is None:
                row = ProjectReplica(pk=pk, account_id=account_id, project_id=project_id, raw_json="{}")

            row.name = payload.get("name")
            row.group_id = payload.get("groupId")
            row.closed = payload.get("closed")
            row.sort_order = payload.get("sortOrder")
            row.etag = payload.get("etag")
            row.modified_time = payload.get("modifiedTime")
            row.kind = payload.get("kind")
            row.view_mode = payload.get("viewMode")
            row.raw_json = json.dumps(payload, ensure_ascii=False)
            row.updated_at = utcnow()
            self.session.add(row)

    def replace_groups(self, account_id: str, groups: list[dict]) -> None:
        incoming = {item.get("id"): item for item in groups if item.get("id")}
        existing = self.session.exec(select(GroupReplica).where(GroupReplica.account_id == account_id)).all()

        for row in existing:
            if row.group_id not in incoming:
                self.session.delete(row)

        for group_id, payload in incoming.items():
            pk = make_pk(account_id, group_id)
            row = self.session.get(GroupReplica, pk)
            if row is None:
                row = GroupReplica(pk=pk, account_id=account_id, group_id=group_id, raw_json="{}")

            row.name = payload.get("name")
            row.deleted = payload.get("deleted")
            row.sort_order = payload.get("sortOrder")
            row.etag = payload.get("etag")
            row.sort_type = payload.get("sortType")
            row.sort_option_json = json.dumps(payload.get("sortOption"), ensure_ascii=False)
            row.raw_json = json.dumps(payload, ensure_ascii=False)
            row.updated_at = utcnow()
            self.session.add(row)

    def update_checkpoint_success(self, account_id: str, checkpoint: int) -> None:
        state = self.get_or_create_checkpoint_state(account_id)
        state.checkpoint = checkpoint
        state.last_status = "success"
        state.last_error = None
        state.error_streak = 0
        state.updated_at = utcnow()
        state.last_success_at = utcnow()
        self.session.add(state)

    def update_checkpoint_error(self, account_id: str, error: str) -> None:
        state = self.get_or_create_checkpoint_state(account_id)
        state.last_status = "error"
        state.last_error = error
        state.error_streak += 1
        state.updated_at = utcnow()
        self.session.add(state)
        self.session.commit()

    def set_checkpoint_status(self, account_id: str, status: str, error: str | None = None) -> None:
        state = self.get_or_create_checkpoint_state(account_id)
        state.last_status = status
        state.last_error = error
        state.updated_at = utcnow()
        self.session.add(state)
        self.session.commit()

    def get_checkpoint_state(self, account_id: str) -> CheckpointState:
        return self.get_or_create_checkpoint_state(account_id)

    def get_lease(self, account_id: str) -> PollerLease | None:
        return self.session.get(PollerLease, account_id)

    def get_row_counts(self, account_id: str) -> dict[str, int]:
        tasks = self.session.exec(
            select(func.count()).select_from(TaskReplica).where(TaskReplica.account_id == account_id)
        ).one()
        projects = self.session.exec(
            select(func.count()).select_from(ProjectReplica).where(ProjectReplica.account_id == account_id)
        ).one()
        groups = self.session.exec(
            select(func.count()).select_from(GroupReplica).where(GroupReplica.account_id == account_id)
        ).one()
        return {
            "tasks": int(tasks),
            "projects": int(projects),
            "groups": int(groups),
        }

    def list_cycles(self, account_id: str, limit: int = 50) -> list[PollCycle]:
        return self.session.exec(
            select(PollCycle)
            .where(PollCycle.account_id == account_id)
            .order_by(PollCycle.started_at.desc())
            .limit(limit)
        ).all()

    def purge_account_replica(self, account_id: str) -> None:
        self.session.exec(delete(TaskReplica).where(TaskReplica.account_id == account_id))
        self.session.exec(delete(ProjectReplica).where(ProjectReplica.account_id == account_id))
        self.session.exec(delete(GroupReplica).where(GroupReplica.account_id == account_id))
        self.session.commit()