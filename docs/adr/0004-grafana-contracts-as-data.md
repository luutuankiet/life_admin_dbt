# Test Grafana dashboards with declarative contracts and one generic runner

Dashboards edited live in Grafana regressed silently: a changed time window,
lost week colours, a query reading the wrong dataset. We export dashboards to
git and assert on them with YAML contracts (`grafana/contracts/`), composed
from reusable packs and checked by one pytest file
(`tests/grafana/test_contracts.py`) in CI.

## Considered options

- **One hand-written test per dashboard.** Rejected: duplicates the same checks across files.
- **Review screenshots by hand or by an agent.** Kept for authoring, but not as a merge gate.
