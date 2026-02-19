from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class PollerSettings(BaseModel):
    db_path: Path = Field(default=Path("EL/ticktick/v3/data/ticktick_replica.db"))
    raw_archive_dir: Path = Field(default=Path("EL/ticktick/v3/data/raw_batches"))
    request_timeout_seconds: int = Field(default=30, ge=5, le=180)
    lease_ttl_seconds: int = Field(default=90, ge=30, le=600)
    poll_interval_seconds: int = Field(default=30, ge=5, le=3600)
    archive_raw_payloads: bool = Field(default=True)

    @classmethod
    def from_env(cls) -> "PollerSettings":
        return cls(
            db_path=Path(os.getenv("TICKTICK_V3_DB_PATH", "EL/ticktick/v3/data/ticktick_replica.db")),
            raw_archive_dir=Path(
                os.getenv("TICKTICK_V3_RAW_ARCHIVE_DIR", "EL/ticktick/v3/data/raw_batches")
            ),
            request_timeout_seconds=int(os.getenv("TICKTICK_V3_REQUEST_TIMEOUT", "30")),
            lease_ttl_seconds=int(os.getenv("TICKTICK_V3_LEASE_TTL", "90")),
            poll_interval_seconds=int(os.getenv("TICKTICK_V3_POLL_INTERVAL", "30")),
            archive_raw_payloads=os.getenv("TICKTICK_V3_ARCHIVE_RAW", "1") == "1",
        )

    def ensure_runtime_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.raw_archive_dir.mkdir(parents=True, exist_ok=True)