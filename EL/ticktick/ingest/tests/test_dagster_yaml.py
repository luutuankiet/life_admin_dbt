"""The shipped ``docker/dagster.yaml`` loads, and its run monitoring fails a run left
STARTED with no worker behind it (a container stop mid-run). Offline."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest
import yaml
from dagster import DagsterEvent, DagsterEventType, DagsterInstance, DagsterRunStatus
from dagster._core.test_utils import create_run_for_test
from dagster._daemon.monitoring import run_monitoring

DAGSTER_YAML = Path(__file__).parents[1] / "docker" / "dagster.yaml"


@pytest.fixture
def instance(tmp_path):
    """The real config with every /state path moved under tmp_path."""
    text = DAGSTER_YAML.read_text().replace("/state", str(tmp_path / "state"))
    home = tmp_path / "home"
    home.mkdir()
    (home / "dagster.yaml").write_text(text)
    with DagsterInstance.from_config(str(home)) as inst:
        yield inst


def test_config_parses_as_yaml():
    assert yaml.safe_load(DAGSTER_YAML.read_text())["run_monitoring"]["enabled"] is True


def test_instance_loads_with_monitoring_daemon(instance):
    assert instance.run_monitoring_enabled
    # The default launcher cannot check worker health, so a STARTED zombie is only
    # ever caught by the runtime limit: it must be set.
    assert not instance.run_launcher.supports_check_run_worker_health
    assert instance.run_monitoring_max_runtime_seconds > 0
    assert instance.run_monitoring_max_resume_run_attempts == 0
    assert "MONITORING" in instance.get_required_daemon_types()
    assert instance.run_coordinator.get_run_queue_config().max_concurrent_runs == 1


class _Workspace:
    def __init__(self, instance):
        self.instance = instance

    def create_request_context(self):
        return None


def _started_run(instance):
    run = create_run_for_test(instance, job_name="ticktick_sync", status=DagsterRunStatus.STARTING)
    instance.report_dagster_event(
        DagsterEvent(DagsterEventType.RUN_START.value, job_name="ticktick_sync"), run.run_id
    )
    assert instance.get_run_by_id(run.run_id).status == DagsterRunStatus.STARTED
    return run


def _monitor(instance, monkeypatch, at: float):
    monkeypatch.setattr(run_monitoring, "get_current_timestamp", lambda: at)
    list(run_monitoring.execute_run_monitoring_iteration(_Workspace(instance), logging.getLogger()))


def test_zombie_started_run_is_failed_after_max_runtime(instance, monkeypatch):
    run = _started_run(instance)
    limit = instance.run_monitoring_max_runtime_seconds

    _monitor(instance, monkeypatch, time.time() + limit - 60)
    assert instance.get_run_by_id(run.run_id).status == DagsterRunStatus.STARTED

    _monitor(instance, monkeypatch, time.time() + limit + 60)
    assert instance.get_run_by_id(run.run_id).status == DagsterRunStatus.FAILURE
