# TickTick v3 Poller

This module implements a disk-backed TickTick v3 replica using SQLModel + Pydantic.

## Why this structure

- `poller/models.py`: SQLModel table schema only (single place to maintain DB schema)
- `poller/schemas.py`: Pydantic request/response schema only (single place to maintain payload contracts)
- `poller/repository.py`: persistence logic
- `poller/service.py`: poller orchestration and checkpoint semantics
- `poller/main.py`: CLI entrypoint

## Quick start

1. Install dependencies (after updating lock):

```bash
uv sync
```

2. Initialize DB schema:

```bash
python -m EL.ticktick.v3.poller.main init-db
```

3. Copy a browser `copy as curl` into a local file (see `config/ticktick_check.curl.example`).

4. Import credentials:

```bash
python -m EL.ticktick.v3.poller.main import-curl --curl-file EL/ticktick/v3/config/ticktick_check.curl
```

5. Run one cycle:

```bash
python -m EL.ticktick.v3.poller.main poll-once
```

6. Run continuous poll loop (default 30s):

```bash
python -m EL.ticktick.v3.poller.main poll-loop --interval 30
```

## Output locations

- SQLite replica DB: `EL/ticktick/v3/data/ticktick_replica.db`
- Raw archived batch payloads: `EL/ticktick/v3/data/raw_batches/`

## Tables

- `credentialprofile`: active browser session profile
- `pollerlease`: single-writer lock with TTL
- `checkpointstate`: durable checkpoint and run health
- `taskreplica`: task entity replica
- `projectreplica`: project entity replica
- `groupreplica`: group entity replica
- `pollcycle`: cycle-level telemetry