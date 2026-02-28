# Grafana Contracts

This directory contains executable, declarative dashboard contracts.

Goals:
- prevent UX and query regressions,
- keep checks reusable through packs,
- run with one command and get dashboard-level failures.

## Structure

- `registry.yaml`: tracked dashboard UID inventory and artifact ownership.
  - `status: active` entries must keep artifacts present.
  - `status: archived` entries are metadata only by default unless `artifact_required: true` is set.
- `packs/`: reusable rule packs shared by many dashboards.
- `dashboards/`: dashboard-specific contract composition.

## Run

First-time setup:

```bash
uv sync --group dev
```

Run contracts:

```bash
uv run --group dev pytest tests/grafana -q
```

## Authoring rules

- Put shared behavior in `packs/`.
- Put dashboard-specific intent in `dashboards/<uid>.yaml`.
- Keep rationale in contract fields so future maintainers know why a rule exists.