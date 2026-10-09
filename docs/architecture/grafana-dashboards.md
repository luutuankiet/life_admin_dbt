---
title: Grafana dashboards, exports and contracts
covers: where the dashboard JSON comes from, why it contains ${DBT_BQ_PROJECT} placeholders, how dashboard regressions are tested
verified: 2026-10-09
---

# Grafana dashboards, exports and contracts

Dashboards are authored live in Grafana. The repository keeps a **read-only
export**, never the source of truth. The flow runs Grafana → git, never the
other way.

| path | what lives there |
|---|---|
| `grafana/scripts/export_grafana_artifacts.py` | pulls dashboards over the HTTP API and normalizes them (`id=null`, `version=1`, `iteration` dropped, deployment values replaced by placeholders) |
| `.github/workflows/grafana_write_back.yml` | manual workflow that runs the exporter and commits the result |
| `grafana/dashboards/gtd-migration/gtd-main-tasks-v3.json` | the one live dashboard |
| `grafana/contracts/registry.yaml` | which dashboards have contracts |
| `grafana/contracts/packs/*.yaml` | reusable check packs (time window, week colours, integer averages, tooltips) |
| `grafana/contracts/dashboards/*.yaml` | per-dashboard composition of packs plus local checks |
| `tests/grafana/test_contracts.py` | the single generic pytest runner |
| `.github/workflows/grafana_contract_ci.yml` | runs the contracts on pull requests |
| `docs/grafana/*.md` | the lookahead chart spec and the guardrail contract guide |

## Placeholders in exported JSON

The exporter replaces the value of `GRAFANA_URL` with `${GRAFANA_URL}` and the
value of `DBT_BQ_PROJECT` with `${DBT_BQ_PROJECT}` before writing. That keeps
the public repo free of the deployment's host and project. **To import a file
back into Grafana, substitute both tokens first.** For example:

```sh
envsubst '${GRAFANA_URL} ${DBT_BQ_PROJECT}' < gtd-main-tasks-v3.json > /tmp/import.json
```

Contract checks that match on a table name match on
`${DBT_BQ_PROJECT}.ticktick_dbt_prod.<table>`, the form that appears in the file.

## Determinism

A re-export with no semantic dashboard change produces no git diff. A diff after
export means something in Grafana really changed.

## Two uv projects

The root `pyproject.toml` holds dbt and the contract tests
(`uv run --group dev pytest tests/grafana -q`). `grafana/scripts/` has its own
`pyproject.toml` and lockfile for the exporter. Run each from its own directory.
