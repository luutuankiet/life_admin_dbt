from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session

from .client import TickTickBatchClient
from .config import PollerSettings
from .repository import ReplicaRepository
from .schemas import PollSummary


class PollerService:
    def __init__(self, settings: PollerSettings, engine):
        self.settings = settings
        self.engine = engine

    def _archive_payload(self, account_id: str, checkpoint: int, payload: dict) -> None:
        if not self.settings.archive_raw_payloads:
            return
        self.settings.ensure_runtime_dirs()
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_path = Path(self.settings.raw_archive_dir) / f"{account_id}__cp_{checkpoint}__{ts}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def _read_checkpoint(self, repo: ReplicaRepository, account_id: str) -> int:
        state = repo.get_or_create_checkpoint_state(account_id)
        return state.checkpoint

    def run_once(self, account_id: str = "default", owner_id: str = "local") -> PollSummary:
        with Session(self.engine) as session:
            repo = ReplicaRepository(session)
            if not repo.try_acquire_lease(account_id, owner_id, self.settings.lease_ttl_seconds):
                raise RuntimeError("Could not acquire lease. Another poller is active.")

            profile = repo.get_active_profile(account_id)
            if profile is None:
                raise RuntimeError("No active credential profile. Run import-curl first.")

            source_checkpoint = self._read_checkpoint(repo, account_id)
            cycle = repo.start_cycle(account_id=account_id, owner_id=owner_id, source_checkpoint=source_checkpoint)

            try:
                client = TickTickBatchClient(profile, timeout_seconds=self.settings.request_timeout_seconds)
                delta = client.fetch_delta(source_checkpoint)
                payload = delta.model_dump()
                self._archive_payload(account_id, delta.checkPoint, payload)

                updates_count = 0
                deletes_count = 0
                projects_count = None
                groups_count = None

                task_bean = delta.syncTaskBean
                if task_bean and not task_bean.empty:
                    for item in task_bean.update:
                        repo.upsert_task_patch(account_id, item)
                        updates_count += 1
                    deletes_count = repo.delete_tasks(account_id, task_bean.delete)

                if delta.projectProfiles is not None:
                    projects_count = len(delta.projectProfiles)
                    repo.replace_projects(account_id, delta.projectProfiles)

                if delta.projectGroups is not None:
                    groups_count = len(delta.projectGroups)
                    repo.replace_groups(account_id, delta.projectGroups)

                state_updated = False
                if task_bean and not task_bean.empty:
                    state_updated = True
                if delta.projectProfiles is not None or delta.projectGroups is not None:
                    state_updated = True

                if state_updated:
                    repo.update_checkpoint_success(account_id, delta.checkPoint)
                else:
                    state = repo.get_or_create_checkpoint_state(account_id)
                    state.last_status = "idle"
                    state.last_error = None
                    state.updated_at = datetime.now(timezone.utc)
                    session.add(state)

                repo.finish_cycle_success(
                    cycle=cycle,
                    response_checkpoint=delta.checkPoint,
                    updates_count=updates_count,
                    deletes_count=deletes_count,
                    projects_count=projects_count,
                    groups_count=groups_count,
                )

                repo.heartbeat_lease(account_id, owner_id, self.settings.lease_ttl_seconds)

                return PollSummary(
                    account_id=account_id,
                    source_checkpoint=source_checkpoint,
                    response_checkpoint=delta.checkPoint,
                    updates_count=updates_count,
                    deletes_count=deletes_count,
                    projects_count=projects_count,
                    groups_count=groups_count,
                    state_updated=state_updated,
                )

            except Exception as exc:  # noqa: BLE001
                session.rollback()
                repo.finish_cycle_error(cycle, str(exc))
                repo.update_checkpoint_error(account_id, str(exc))
                raise

    def run_loop(self, account_id: str = "default", owner_id: str = "local") -> None:
        while True:
            summary = self.run_once(account_id=account_id, owner_id=owner_id)
            print(summary.model_dump_json())
            time.sleep(self.settings.poll_interval_seconds)