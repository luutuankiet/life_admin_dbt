from __future__ import annotations

import argparse
from pathlib import Path

from sqlmodel import Session

from .auth import parse_curl_profile
from .config import PollerSettings
from .db import build_engine, init_db
from .repository import ReplicaRepository
from .service import PollerService


def cmd_init_db(args) -> None:
    settings = PollerSettings.from_env()
    engine = build_engine(settings)
    init_db(engine)
    print(f"Initialized database at {settings.db_path}")


def cmd_import_curl(args) -> None:
    settings = PollerSettings.from_env()
    engine = build_engine(settings)
    init_db(engine)

    curl_text = Path(args.curl_file).read_text(encoding="utf-8")
    profile_in = parse_curl_profile(curl_text, account_id=args.account)

    with Session(engine) as session:
        repo = ReplicaRepository(session)
        profile = repo.upsert_active_profile(profile_in)

    print(f"Saved active credential profile {profile.id} for account={args.account}")


def cmd_poll_once(args) -> None:
    settings = PollerSettings.from_env()
    engine = build_engine(settings)
    init_db(engine)

    service = PollerService(settings, engine)
    summary = service.run_once(account_id=args.account, owner_id=args.owner)
    print(summary.model_dump_json())


def cmd_poll_loop(args) -> None:
    settings = PollerSettings.from_env()
    if args.interval is not None:
        settings.poll_interval_seconds = args.interval

    engine = build_engine(settings)
    init_db(engine)

    service = PollerService(settings, engine)
    service.run_loop(account_id=args.account, owner_id=args.owner)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TickTick v3 poller")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_cmd = subparsers.add_parser("init-db", help="Create SQLite schema")
    init_cmd.set_defaults(func=cmd_init_db)

    import_cmd = subparsers.add_parser("import-curl", help="Import credential profile from copied curl")
    import_cmd.add_argument("--curl-file", required=True, help="Path to file containing curl command text")
    import_cmd.add_argument("--account", default="default")
    import_cmd.set_defaults(func=cmd_import_curl)

    once_cmd = subparsers.add_parser("poll-once", help="Run one polling cycle")
    once_cmd.add_argument("--account", default="default")
    once_cmd.add_argument("--owner", default="local")
    once_cmd.set_defaults(func=cmd_poll_once)

    loop_cmd = subparsers.add_parser("poll-loop", help="Run polling loop")
    loop_cmd.add_argument("--account", default="default")
    loop_cmd.add_argument("--owner", default="local")
    loop_cmd.add_argument("--interval", type=int, default=None, help="Override poll interval seconds")
    loop_cmd.set_defaults(func=cmd_poll_loop)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()