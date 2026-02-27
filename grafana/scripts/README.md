# Grafana Artifact Export Script

This script exports dashboard JSON from a live Grafana instance via HTTP API.

Provisioning artifacts are optional flags (`--include-providers`, `--include-datasources`).

## Runtime

Run from any machine that can reach your Grafana URL and has a valid service account token.

- Does not require container shell access
- Does not require Grafana CLI
- Uses standard Grafana API endpoints

## Required env vars

- `GRAFANA_URL` (example: `https://grafana.example.com`)
- `GRAFANA_SERVICE_ACCOUNT_TOKEN`

## Usage

```bash
cd grafana/scripts
uv run python export_grafana_artifacts.py
```

Optional:

```bash
uv run python export_grafana_artifacts.py \
  --dashboard-uids gtd-weekly-review-v3
```

## Outputs

Default output:

- Dashboards: `grafana/dashboards/<folder>/<uid>.json`

Optional outputs:

- Providers: `grafana/provisioning/dashboards/<folder>.yaml` (`--include-providers`)
- Datasource snapshot: `grafana/provisioning/datasources/from-api-snapshot.yaml` (`--include-datasources`)

## Notes

- The datasource snapshot uses placeholders for secure fields because Grafana API does not return secret values.
- Review `from-api-snapshot.yaml` before using it as active provisioning input.
- Script normalizes dashboard `id` to `null`, resets `version` to `1`, and removes `iteration` for stable diffs.
- For read-only Git versioning of dashboard shape, you only need the default dashboard export mode.