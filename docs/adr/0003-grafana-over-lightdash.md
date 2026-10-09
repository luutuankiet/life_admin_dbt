# Grafana for dashboards, dbt for semantics; Lightdash retired

Lightdash put metrics in dbt YAML and gave agents no practical write path, so
dashboard work stalled. We moved joins and metrics into dbt marts
(`fct_tasks_v3_*`) and made Grafana a thin visualization layer that agents can
edit through its API.

## Considered options

- **Stay on Lightdash.** Rejected: metrics buried in YAML, no agent write access.
- **A static report tool (Evidence.dev).** Parked: fine for periodic reports, not for a live planning view.

## Consequences

`models/lightdash_exposures.yml`, `lightdash/` and `LD_write_back.yml` are now
legacy and can be deleted when nothing references them.
