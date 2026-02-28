from __future__ import annotations

import fnmatch
import json
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = ROOT_DIR / "grafana" / "contracts"
PACKS_DIR = CONTRACTS_DIR / "packs"
REGISTRY_PATH = CONTRACTS_DIR / "registry.yaml"


TOKEN_RE = re.compile(r"^(?P<key>[A-Za-z0-9_-]+)(?:\[(?P<index>\d+)\])?$")
OVERRIDE_SELECTOR_RE = re.compile(r"^panel\.override\[(?P<series>[^\]]+)\]\.(?P<field>.+)$")


@dataclass
class ValidationIssue:
    severity: str
    dashboard_uid: str
    panel_id: int | None
    check_id: str
    message: str


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file_handle:
        payload = yaml.safe_load(file_handle) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Expected YAML object at {path}")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _to_repo_path(path_string: str) -> Path:
    path = Path(path_string)
    if path.is_absolute():
        return path
    return (ROOT_DIR / path).resolve()


def _to_repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT_DIR).as_posix()


def _resolve_path(value: Any, path_expr: str) -> Any:
    current = value
    for token in path_expr.split("."):
        match = TOKEN_RE.match(token)
        if not match:
            raise KeyError(f"Invalid path token '{token}' in '{path_expr}'")

        key = match.group("key")
        index = match.group("index")

        if not isinstance(current, dict):
            raise KeyError(f"Cannot access key '{key}' on non-object value")
        if key not in current:
            raise KeyError(f"Missing key '{key}' while resolving '{path_expr}'")

        current = current[key]

        if index is not None:
            if not isinstance(current, list):
                raise KeyError(f"Key '{key}' is not a list while resolving '{path_expr}'")
            idx = int(index)
            if idx >= len(current):
                raise KeyError(f"Index {idx} out of range for key '{key}'")
            current = current[idx]

    return current


def _find_panel(dashboard: dict[str, Any], panel_id: int) -> dict[str, Any]:
    for panel in dashboard.get("panels", []):
        if panel.get("id") == panel_id:
            return panel
    raise KeyError(f"Panel id {panel_id} not found")


def _find_override(panel: dict[str, Any], series_name: str) -> dict[str, Any] | None:
    overrides = panel.get("fieldConfig", {}).get("overrides", [])
    for override in overrides:
        matcher = override.get("matcher", {})
        if matcher.get("options") == series_name:
            return override
    return None


def _find_override_property(override: dict[str, Any], property_id: str) -> Any:
    for prop in override.get("properties", []):
        if prop.get("id") == property_id:
            return prop.get("value")
    return None


def _resolve_override_field(panel: dict[str, Any], series: str, field: str) -> Any:
    override = _find_override(panel, series)
    if field == "exists":
        return override is not None

    if override is None:
        return None

    if field == "color":
        color_value = _find_override_property(override, "color")
        if isinstance(color_value, dict):
            return color_value.get("fixedColor") or color_value.get("mode")
        return color_value

    field_map: dict[str, tuple[str, str | None]] = {
        "decimals": ("decimals", None),
        "line_width": ("custom.lineWidth", None),
        "fill_opacity": ("custom.fillOpacity", None),
        "line_style": ("custom.lineStyle", None),
        "line_style.fill": ("custom.lineStyle", "fill"),
        "line_style.dash": ("custom.lineStyle", "dash"),
        "show_points": ("custom.showPoints", None),
        "hide_from.legend": ("custom.hideFrom", "legend"),
        "hide_from.tooltip": ("custom.hideFrom", "tooltip"),
        "hide_from.viz": ("custom.hideFrom", "viz"),
    }

    if field not in field_map:
        raise KeyError(f"Unknown override field '{field}'")

    property_id, nested_key = field_map[field]
    base_value = _find_override_property(override, property_id)

    if nested_key is None:
        return base_value

    if not isinstance(base_value, dict):
        return None

    return base_value.get(nested_key)


def _resolve_selector(
    selector: str,
    dashboard: dict[str, Any],
    panel: dict[str, Any] | None,
) -> Any:
    if selector == "panel.query":
        if panel is None:
            raise KeyError("panel.query requires a panel context")
        return _resolve_path(panel, "targets[0].rawSql")

    override_match = OVERRIDE_SELECTOR_RE.match(selector)
    if override_match:
        if panel is None:
            raise KeyError("panel.override selectors require a panel context")
        series = override_match.group("series")
        field = override_match.group("field")
        return _resolve_override_field(panel, series, field)

    if selector.startswith("dashboard."):
        return _resolve_path(dashboard, selector[len("dashboard.") :])

    if selector.startswith("panel."):
        if panel is None:
            raise KeyError("panel selector requires a panel context")
        return _resolve_path(panel, selector[len("panel.") :])

    raise KeyError(f"Unknown selector namespace in '{selector}'")


def _evaluate_op(op: str, actual: Any, expected: Any) -> bool:
    if op == "equals":
        return actual == expected

    if op == "not_equals":
        return actual != expected

    if op == "contains_all":
        haystack = "" if actual is None else str(actual)
        return all(str(item) in haystack for item in expected)

    if op == "contains_any":
        haystack = "" if actual is None else str(actual)
        return any(str(item) in haystack for item in expected)

    if op == "contains_none":
        haystack = "" if actual is None else str(actual)
        return all(str(item) not in haystack for item in expected)

    if op == "regex":
        haystack = "" if actual is None else str(actual)
        return re.search(str(expected), haystack) is not None

    if op == "in":
        return actual in expected

    if op == "not_in":
        return actual not in expected

    if op == "exists":
        expected_value = True if expected is None else bool(expected)
        return (actual is not None) == expected_value

    raise ValueError(f"Unsupported operation '{op}'")


def _pack_path(pack_name: str) -> Path:
    return PACKS_DIR / f"{pack_name}.yaml"


def _build_checkset(panel_contract: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    for pack_name in panel_contract.get("use_packs", []):
        pack_path = _pack_path(pack_name)
        if not pack_path.exists():
            raise FileNotFoundError(f"Pack not found: {pack_path}")
        pack_payload = _load_yaml(pack_path)
        checks.extend(pack_payload.get("checks", []))

    checks.extend(panel_contract.get("checks", []))
    return checks


def _check_registry_consistency(registry: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    dashboard_entries = registry.get("dashboards", [])
    policy = registry.get("policy", {})

    unmanaged_mode = str(policy.get("unmanaged_artifacts", "error")).lower()
    ignore_globs = policy.get("ignore_artifact_globs", [])

    registered_paths: set[Path] = set()

    for entry in dashboard_entries:
        uid = entry.get("uid", "unknown")
        status = str(entry.get("status", "active")).lower()
        contracts = entry.get("contracts", [])
        artifact_path_raw = str(entry.get("artifact_path", "")).strip()

        if not artifact_path_raw:
            if status == "active":
                issues.append(
                    ValidationIssue(
                        severity="error",
                        dashboard_uid=uid,
                        panel_id=None,
                        check_id="registry_artifact_path_present",
                        message="Active dashboard is missing artifact_path in registry",
                    )
                )
            continue

        artifact_path = _to_repo_path(artifact_path_raw)
        registered_paths.add(artifact_path)

        artifact_required = bool(
            entry.get("artifact_required", status == "active" or bool(contracts))
        )

        if artifact_required and not artifact_path.exists():
            severity = "error" if status == "active" else "warn"
            issues.append(
                ValidationIssue(
                    severity=severity,
                    dashboard_uid=uid,
                    panel_id=None,
                    check_id="registry_artifact_exists",
                    message=f"Missing artifact file: {_to_repo_relative(artifact_path)}",
                )
            )

    all_artifacts = sorted((ROOT_DIR / "grafana" / "dashboards").rglob("*.json"))

    for artifact_path in all_artifacts:
        if artifact_path in registered_paths:
            continue

        artifact_rel = _to_repo_relative(artifact_path)
        ignored = any(fnmatch.fnmatch(artifact_rel, pattern) for pattern in ignore_globs)
        if ignored:
            continue

        if unmanaged_mode == "ignore":
            continue

        severity = "warn" if unmanaged_mode == "warn" else "error"
        issues.append(
            ValidationIssue(
                severity=severity,
                dashboard_uid="registry",
                panel_id=None,
                check_id="registry_unmanaged_artifact",
                message=f"Unmanaged artifact not in registry: {artifact_rel}",
            )
        )

    return issues


def _run_panel_checks(
    dashboard_uid: str,
    dashboard_payload: dict[str, Any],
    panel_contract: dict[str, Any],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    panel_id = int(panel_contract["id"])
    panel = _find_panel(dashboard_payload, panel_id)

    checks = _build_checkset(panel_contract)

    for check in checks:
        check_id = check.get("id", "unknown_check")
        selector = check.get("selector")
        op = check.get("op")
        expected = check.get("expected")
        severity = check.get("severity", "error")

        try:
            actual = _resolve_selector(selector, dashboard_payload, panel)
            passed = _evaluate_op(op, actual, expected)
        except Exception as exc:  # noqa: BLE001
            issues.append(
                ValidationIssue(
                    severity="error",
                    dashboard_uid=dashboard_uid,
                    panel_id=panel_id,
                    check_id=check_id,
                    message=f"Execution error for selector '{selector}': {exc}",
                )
            )
            continue

        if not passed:
            issues.append(
                ValidationIssue(
                    severity=severity,
                    dashboard_uid=dashboard_uid,
                    panel_id=panel_id,
                    check_id=check_id,
                    message=(
                        f"Check failed: selector='{selector}' op='{op}' "
                        f"expected={expected!r} actual={actual!r}"
                    ),
                )
            )

    return issues


def _run_dashboard_contract(
    entry: dict[str, Any],
    dashboard_payload: dict[str, Any],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    dashboard_uid = entry["uid"]

    for contract_path_string in entry.get("contracts", []):
        contract_path = _to_repo_path(contract_path_string)
        if not contract_path.exists():
            issues.append(
                ValidationIssue(
                    severity="error",
                    dashboard_uid=dashboard_uid,
                    panel_id=None,
                    check_id="contract_file_exists",
                    message=f"Missing contract file: {_to_repo_relative(contract_path)}",
                )
            )
            continue

        contract_payload = _load_yaml(contract_path)
        contract_uid = contract_payload.get("dashboard_uid")
        if contract_uid != dashboard_uid:
            issues.append(
                ValidationIssue(
                    severity="error",
                    dashboard_uid=dashboard_uid,
                    panel_id=None,
                    check_id="contract_uid_matches_registry",
                    message=(
                        f"Contract UID mismatch: contract has '{contract_uid}', "
                        f"registry has '{dashboard_uid}'"
                    ),
                )
            )

        for panel_contract in contract_payload.get("panels", []):
            issues.extend(_run_panel_checks(dashboard_uid, dashboard_payload, panel_contract))

    return issues


def _format_issue(issue: ValidationIssue) -> str:
    panel_part = f" panel={issue.panel_id}" if issue.panel_id is not None else ""
    return (
        f"[{issue.severity}] dashboard={issue.dashboard_uid}{panel_part} "
        f"check={issue.check_id} - {issue.message}"
    )


def test_grafana_dashboard_contracts() -> None:
    registry = _load_yaml(REGISTRY_PATH)
    issues: list[ValidationIssue] = []

    issues.extend(_check_registry_consistency(registry))

    for entry in registry.get("dashboards", []):
        if entry.get("status", "active") != "active":
            continue

        dashboard_uid = entry.get("uid", "unknown")
        artifact_path = _to_repo_path(entry.get("artifact_path", ""))

        if not artifact_path.exists():
            continue

        dashboard_payload = _load_json(artifact_path)
        issues.extend(_run_dashboard_contract(entry, dashboard_payload))

        if not entry.get("contracts"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    dashboard_uid=dashboard_uid,
                    panel_id=None,
                    check_id="active_dashboard_has_contract",
                    message="Active dashboard has no contract files declared",
                )
            )

    warnings_only = [issue for issue in issues if issue.severity == "warn"]
    errors = [issue for issue in issues if issue.severity != "warn"]

    for issue in warnings_only:
        warnings.warn(_format_issue(issue), stacklevel=1)

    assert not errors, "Grafana contract failures:\n" + "\n".join(
        _format_issue(issue) for issue in errors
    )