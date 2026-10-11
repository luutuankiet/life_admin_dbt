"""``python -m ticktick_ingest.cli sync|backfill|reset|rebuild-gate``.

Reads configuration from the environment (see ``pipeline.py``). Prints the run summary
as JSON. Exit code 2 when TickTick rejects the cookie.
"""

from __future__ import annotations

import argparse
import json
import sys

from .client import AuthRejected
from .pipeline import make_pipeline, run_sync, state_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ticktick_ingest.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync", help="fetch the delta since the stored checkpoint")
    sync.add_argument("--kind", choices=("hint", "safety"), default="hint")
    sub.add_parser("backfill", help="sync, then page closed tasks down to the floor")
    sub.add_parser("reset", help="sync from checkpoint 0, merging every task")
    sub.add_parser("rebuild-gate", help="delete gate.db and rebuild it from the tasks table")
    for p in sub.choices.values():
        p.add_argument("--run-id", default=None, help="defaults to manual-<uuid>")
    args = parser.parse_args(argv)

    if args.command == "rebuild-gate":
        from .gate import Gate

        path = state_dir() / "gate.db"
        path.unlink(missing_ok=True)
        pipeline = make_pipeline()
        pipeline.sync_destination()
        gate = Gate(path)
        n = gate.rebuild_from_bigquery(pipeline)
        gate.close()
        print(json.dumps({"gate": str(path), "fingerprints": n}))
        return 0

    kind = args.kind if args.command == "sync" else args.command
    try:
        summary = run_sync(kind, run_id=args.run_id)
    except AuthRejected as exc:
        print(f"cookie rejected: paste a fresh t ({exc})", file=sys.stderr)
        return 2
    print(json.dumps(summary.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
