# Life Admin dbt Platform

*Initialized: 2026-02-18*

## What This Is

A personal data platform for GTD-driven life decisions. Extracts task data from TickTick (main GTD system) and Todoist (habits), transforms via dbt, and surfaces insights through Lightdash dashboards. Designed to make daily/weekly GTD reviews data-driven — see task distribution across projects, areas of responsibility, and time horizons at a glance.

The platform is built for a single developer on GCP free tier, prioritizing low maintenance overhead and zero-cost idle state.

## Core Value

**The dashboard must be fast enough to use during active planning sessions.** If you reschedule tasks in TickTick, the change should appear in seconds — not minutes. The feedback loop between action and insight must be tight enough that the dashboard feels like an extension of your task manager, not a reporting afterthought.

## Success Criteria

Project succeeds when:

- [ ] Data freshness: TickTick changes visible in dashboard within **seconds**
- [ ] Query latency: Dashboard queries complete in <2 seconds
- [ ] Dashboard load: Initial load <5 seconds
- [ ] Pipeline observability: Data freshness indicator visible in dashboard
- [ ] Snapshot resilience: Historical completion data is backed up and recoverable
- [ ] Reproducibility: New data source (e.g., YNAB) can be added without manual bucket/schema setup

## Context

### GTD Horizons (the "why")

The data model maps to David Allen's 6 Horizons of Focus:
- **Ground:** Calendar/actions (individual tasks)
- **Horizon 1:** Projects (multi-step commitments)
- **Horizon 2:** Areas of focus (folders in TickTick — 4-7 major responsibilities)
- **Horizon 3:** 1-3 year goals (not yet modeled — qualitative)
- **Horizon 4-5:** Vision/purpose (not yet modeled — qualitative)

### Current Data Sources

| Source | Purpose | Status |
|--------|---------|--------|
| TickTick | Main GTD system (tasks, projects, folders) | Active |
| Todoist | Habit/recurring tasks | Active |
| YNAB | Financial decisions | Roadmap |

### Current Architecture

```
TickTick API ──(rate limited: ~1 min full extract)──▶ GHA (every 15 min)
                                                          │
                                                          ▼
                                                    DuckDB snapshot
                                                          │
                                                          ▼
                                                    GCS bucket (JSONL)
                                                          │
                                                          ▼
                                              BigQuery external tables
                                                    (views only)
                                                          │
                                                          ▼
                                              Lightdash (EU VM) ◀── User (Vietnam)
```

### Critical Dependency: Snapshot-based Completion Tracking

TickTick API does not expose task completion metadata. Completed tasks simply disappear from the endpoint. The pipeline uses **SCD2 snapshots** to infer completion:
- Task present in snapshot N, absent in snapshot N+1 → marked as "done"
- `done_time` inferred from `dbt_valid_to` timestamp

**This makes the snapshot table irreplaceable.** It cannot be rebuilt from the API — historical completion data would be lost. Current mitigation: snapshot data persisted to GCS bucket (backup not yet automated).

## Constraints

| Constraint | Detail |
|------------|--------|
| Solo developer | Maintenance overhead must stay minimal |
| GCP free tier | No persistent compute; minimize BQ extraction costs |
| TickTick API rate limit | 60 requests/min → ~1 min for full extract (60+ projects) |
| TickTick API limitation | No completion metadata; snapshot inference required |
| Snapshot is source of truth | Contains historical "done" states not recoverable from API |
| Lightdash latency | Currently EU-hosted; user in Asia; homelab is viable alternative |

## Priority Order (Current)

1. **A — Real-time data freshness** (seconds, not minutes)
2. **B — Dashboard/query performance** (EU→Asia latency)
3. **D — Consolidate architecture** (two-branch setup, snapshot fragility)
4. **C — Pipeline reproducibility** (for onboarding new sources)

## Research Questions (Captured for Later)

- [ ] Does TickTick API support webhooks for real-time push?
- [ ] If not, what's the fastest polling strategy within rate limits?
- [ ] Can we detect deltas (changed tasks only) to avoid full extract?
- [ ] Lightdash Asia hosting options (GCP asia-southeast1 vs homelab)

---

*This document is the "why" — see ARCHITECTURE.md for the "how".*


## 2026-02-22 Pivot Update - dbt + Grafana, Agent-First Dashboard Workflow

The project direction is now operationally centered on **dbt for semantic logic** and **Grafana for dashboard interaction**, with MCP write capability as a first-class requirement for human+agent pair programming.

### What changed

- Lightdash is no longer the primary dashboard execution layer for ongoing migration work.
- Dashboard development now happens live in Grafana through MCP-assisted iteration.
- Dashboard JSON is exported to Git as read-only artifact memory so future agents can reconstruct intent and continue safely.

### Why this matters

- Preserves fast feedback loops during planning sessions while enabling agent collaboration on dashboard lifecycle.
- Prevents semantic drift by moving joins/fields/metrics logic into dbt models and keeping BI queries thin.
- Gives deterministic handoff context without requiring UI archaeology.

### Updated success criteria for migration phase

- [ ] Agents can create/update dashboard slices via Grafana MCP with user-guided pair workflow.
- [ ] Dashboard artifacts are exported and committed to Git after meaningful dashboard changes.
- [ ] First MVP migration for Lightdash `main tasks` tab is implemented with dbt semantic push-left.
- [ ] Grafana panels read thin dbt semantic marts rather than embedding heavy business logic.