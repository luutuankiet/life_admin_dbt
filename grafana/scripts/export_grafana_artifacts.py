#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests
import yaml
from dotenv import load_dotenv


DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_DASHBOARD_LIMIT = 5000


def slugify(value: str) -> str:
    text = value.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "general"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Grafana dashboards to repo files (optionally export provisioning artifacts)"
    )
    parser.add_argument(
        "--grafana-url",
        default=os.getenv("GRAFANA_URL"),
        help="Grafana base URL, e.g. https://grafana.example.com",
    )
    parser.add_argument(
        "--grafana-token",
        default=(
            os.getenv("GRAFANA_SERVICE_ACCOUNT_TOKEN")
            or os.getenv("GRAFANA_TOKEN")
            or os.getenv("GRAFANA_API_TOKEN")
        ),
        help="Grafana service account token",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Repository root path (default: auto-detected from this script location)",
    )
    parser.add_argument(
        "--dashboard-limit",
        type=int,
        default=DEFAULT_DASHBOARD_LIMIT,
        help="Maximum dashboards to fetch from /api/search",
    )
    parser.add_argument(
        "--dashboard-uids",
        nargs="*",
        default=[],
        help="Optional explicit dashboard UIDs to export",
    )
    parser.add_argument(
        "--include-providers",
        action="store_true",
        help="Also generate provisioning dashboard provider YAML files",
    )
    parser.add_argument(
        "--include-datasources",
        action="store_true",
        help="Also generate datasource snapshot YAML",
    )
    return parser.parse_args()


class GrafanaClient:
    def __init__(self, base_url: str, token: str) -> None:
        if not base_url:
            raise ValueError("Missing --grafana-url (or GRAFANA_URL)")
        if not token:
            raise ValueError(
                "Missing --grafana-token (or GRAFANA_SERVICE_ACCOUNT_TOKEN/GRAFANA_TOKEN)"
            )

        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        response = self.session.get(url, params=params, timeout=DEFAULT_TIMEOUT_SECONDS)
        if response.status_code >= 400:
            raise RuntimeError(
                f"GET {path} failed ({response.status_code}): {response.text[:500]}"
            )
        return response.json()

    def list_dashboards(self, limit: int) -> list[dict[str, Any]]:
        payload = self.get(
            "/api/search",
            params={"query": "", "type": "dash-db", "limit": limit},
        )
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected /api/search response shape")
        return payload

    def get_dashboard(self, uid: str) -> dict[str, Any]:
        payload = self.get(f"/api/dashboards/uid/{uid}")
        if not isinstance(payload, dict) or "dashboard" not in payload:
            raise RuntimeError(f"Unexpected dashboard payload for uid={uid}")
        return payload

    def list_datasources(self) -> list[dict[str, Any]]:
        payload = self.get("/api/datasources")
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected /api/datasources response shape")
        return payload


def normalize_dashboard_json(dashboard: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(json.dumps(dashboard))
    data["id"] = None
    if "version" in data:
        data["version"] = 1
    data.pop("iteration", None)
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_yaml(path: Path, payload: dict[str, Any], header: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)
    if header:
        content = header + "\n" + content
    path.write_text(content, encoding="utf-8")


def build_provider(folder_title: str, folder_uid: str | None, dir_name: str) -> dict[str, Any]:
    provider: dict[str, Any] = {
        "name": dir_name,
        "orgId": 1,
        "folder": folder_title if folder_uid else "",
        "type": "file",
        "disableDeletion": True,
        "updateIntervalSeconds": 30,
        "allowUiUpdates": True,
        "options": {
            "path": f"/etc/grafana/dashboards/{dir_name}",
        },
    }
    if folder_uid:
        provider["folderUid"] = folder_uid
    return provider


def export_dashboards(
    client: GrafanaClient,
    dashboards_root: Path,
    providers_root: Path,
    dashboard_limit: int,
    explicit_uids: list[str],
    include_providers: bool,
) -> tuple[int, int]:
    provider_groups: dict[str, dict[str, Any]] = {}
    dashboards_written = 0

    if explicit_uids:
        dashboard_refs = [{"uid": uid} for uid in explicit_uids]
    else:
        dashboard_refs = client.list_dashboards(dashboard_limit)

    for item in dashboard_refs:
        uid = item.get("uid")
        if not uid:
            continue

        payload = client.get_dashboard(uid)
        dashboard = payload["dashboard"]
        meta = payload.get("meta", {})

        folder_uid = meta.get("folderUid") or None
        folder_title = meta.get("folderTitle") or "General"
        dir_name = slugify(folder_uid or folder_title)

        provider_groups.setdefault(
            dir_name,
            {
                "folder_title": folder_title,
                "folder_uid": folder_uid,
            },
        )

        out_path = dashboards_root / dir_name / f"{uid}.json"
        write_json(out_path, normalize_dashboard_json(dashboard))
        dashboards_written += 1

    providers_written = 0
    if include_providers:
        for dir_name, meta in provider_groups.items():
            provider_payload = {
                "apiVersion": 1,
                "providers": [
                    build_provider(
                        folder_title=meta["folder_title"],
                        folder_uid=meta["folder_uid"],
                        dir_name=dir_name,
                    )
                ],
            }
            provider_path = providers_root / f"{dir_name}.yaml"
            write_yaml(provider_path, provider_payload)
            providers_written += 1

    return dashboards_written, providers_written


def sanitize_datasource(ds: dict[str, Any]) -> dict[str, Any]:
    keep_keys = [
        "name",
        "uid",
        "type",
        "access",
        "orgId",
        "url",
        "user",
        "database",
        "basicAuth",
        "basicAuthUser",
        "withCredentials",
        "isDefault",
        "editable",
        "version",
        "jsonData",
    ]
    out = {k: ds[k] for k in keep_keys if k in ds}
    if "secureJsonFields" in ds:
        fields = [k for k, v in ds["secureJsonFields"].items() if v]
        if fields:
            out["secureJsonData"] = {
                key: "__SET_MANUALLY_OR_VIA_ENV__" for key in fields
            }
    return out


def export_datasources(client: GrafanaClient, datasources_file: Path) -> int:
    datasources = client.list_datasources()
    payload = {
        "apiVersion": 1,
        "datasources": [sanitize_datasource(ds) for ds in datasources],
    }
    header = (
        "# Generated snapshot from Grafana API.\n"
        "# Review secureJsonData placeholders before applying provisioning."
    )
    write_yaml(datasources_file, payload, header=header)
    return len(datasources)


def main() -> int:
    load_dotenv()
    args = parse_args()

    try:
        client = GrafanaClient(args.grafana_url, args.grafana_token)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    repo_root = Path(args.repo_root).resolve()
    grafana_root = repo_root / "grafana"

    dashboards_root = grafana_root / "dashboards"
    providers_root = grafana_root / "provisioning" / "dashboards"
    datasources_file = (
        grafana_root / "provisioning" / "datasources" / "from-api-snapshot.yaml"
    )

    try:
        dashboards_written, providers_written = export_dashboards(
            client=client,
            dashboards_root=dashboards_root,
            providers_root=providers_root,
            dashboard_limit=args.dashboard_limit,
            explicit_uids=args.dashboard_uids,
            include_providers=args.include_providers,
        )

        datasources_written = 0
        if args.include_datasources:
            datasources_written = export_datasources(client, datasources_file)

    except Exception as exc:  # noqa: BLE001
        print(f"export failed: {exc}", file=sys.stderr)
        return 1

    print(
        "export complete:\n"
        f"- dashboards: {dashboards_written}\n"
        f"- providers: {providers_written}\n"
        f"- datasources: {datasources_written}"
    )
    print(f"output root: {grafana_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())