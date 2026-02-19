from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


def _resolve_v3_root() -> Path:
    env_root = os.getenv("TICKTICK_V3_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    monorepo_path = Path("EL/ticktick/v3")
    if monorepo_path.exists():
        return monorepo_path.resolve()

    return Path.cwd().resolve()


V3_ROOT = _resolve_v3_root()
DEFAULT_DB_PATH = V3_ROOT / "data" / "ticktick_replica.db"
DEFAULT_RAW_ARCHIVE_DIR = V3_ROOT / "data" / "raw_batches"


class PollerSettings(BaseModel):
    db_path: Path = Field(default=DEFAULT_DB_PATH)
    raw_archive_dir: Path = Field(default=DEFAULT_RAW_ARCHIVE_DIR)
    request_timeout_seconds: int = Field(default=30, ge=5, le=180)
    lease_ttl_seconds: int = Field(default=90, ge=30, le=600)
    poll_interval_seconds: int = Field(default=30, ge=5, le=3600)
    auth_pause_seconds: int = Field(default=300, ge=30, le=86400)
    archive_raw_payloads: bool = Field(default=True)
    raw_retention_hours: int = Field(default=24, ge=1, le=720)

    # GCS emitter
    gcs_emit_enabled: bool = Field(default=False)
    gcs_bucket: str = Field(default="")
    gcs_key: str = Field(default="")
    gcs_secret: str = Field(default="")
    gcs_prefix: str = Field(default="ticktick/v3")

    @classmethod
    def from_env(cls) -> "PollerSettings":
        return cls(
            db_path=Path(os.getenv("TICKTICK_V3_DB_PATH", str(DEFAULT_DB_PATH))),
            raw_archive_dir=Path(os.getenv("TICKTICK_V3_RAW_ARCHIVE_DIR", str(DEFAULT_RAW_ARCHIVE_DIR))),
            request_timeout_seconds=int(os.getenv("TICKTICK_V3_REQUEST_TIMEOUT", "30")),
            lease_ttl_seconds=int(os.getenv("TICKTICK_V3_LEASE_TTL", "90")),
            poll_interval_seconds=int(os.getenv("TICKTICK_V3_POLL_INTERVAL", "30")),
            auth_pause_seconds=int(os.getenv("TICKTICK_V3_AUTH_PAUSE_SECONDS", "300")),
            archive_raw_payloads=os.getenv("TICKTICK_V3_ARCHIVE_RAW", "1") == "1",
            raw_retention_hours=int(os.getenv("TICKTICK_V3_RAW_RETENTION_HOURS", "24")),
            gcs_emit_enabled=os.getenv("TICKTICK_V3_GCS_EMIT_ENABLED", "0") == "1",
            gcs_bucket=os.getenv("GCS_RAW_BUCKET", ""),
            gcs_key=os.getenv("GCS_KEY", ""),
            gcs_secret=os.getenv("GCS_SECRET", ""),
            gcs_prefix=os.getenv("TICKTICK_V3_GCS_PREFIX", "ticktick/v3"),
        )

    def ensure_runtime_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.raw_archive_dir.mkdir(parents=True, exist_ok=True)