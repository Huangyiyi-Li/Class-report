from pathlib import Path

import pytest

from worker.config import WorkerConfig, evaluate_startup_gate, validate_data_root


def bound_config(data_root="D:/ClassroomRecorderData"):
    return WorkerConfig(
        data_root=data_root,
        device_no="device-1",
        school_id=7,
        location_id="room-101",
        location_name="一班",
        base_url="https://offline.invalid",
    )


def test_defaults_contain_no_school_or_credentials(tmp_path: Path):
    config = WorkerConfig.load(tmp_path / "missing.json")
    assert config.school_id is None
    assert config.location_id == ""
    assert config.username == ""
    assert config.password == ""
    assert config.mirror_server_url == ""


def test_rejects_system_drive_data_root(tmp_path: Path):
    with pytest.raises(ValueError, match="非系统盘"):
        validate_data_root(Path("C:/ClassroomRecorderData"), "C:")


def test_rejects_data_root_without_drive():
    with pytest.raises(ValueError, match="非系统盘"):
        validate_data_root(Path("ClassroomRecorderData"), "C:")


def test_rejects_system_drive_case_insensitively():
    with pytest.raises(ValueError, match="非系统盘"):
        validate_data_root(Path("c:/ClassroomRecorderData"), "C:")


def test_normalizes_system_drive_with_forward_slash():
    with pytest.raises(ValueError, match="非系统盘"):
        validate_data_root(Path("C:/ClassroomRecorderData"), "c:/")


def test_accepts_non_system_drive_data_root():
    validate_data_root(Path("D:/ClassroomRecorderData"), "C:")


def test_save_atomic_persists_worker_settings(tmp_path: Path):
    path = tmp_path / "worker-config.json"
    config = WorkerConfig(
        data_root="D:/Recorder",
        auto_record_enabled=True,
        input_device="Microphone 2",
    )

    config.save_atomic(path)

    assert WorkerConfig.load(path) == config
    assert not path.with_suffix(".json.tmp").exists()


@pytest.mark.parametrize("data_root", ["", "ClassroomRecorderData", "C:/Recorder"])
def test_startup_gate_rejects_empty_relative_and_system_drive_roots(data_root):
    gate = evaluate_startup_gate(bound_config(data_root), "C:")

    assert gate.allowed is False
    assert gate.health == "storage_unavailable"


def test_startup_gate_rejects_unwritable_storage(monkeypatch):
    monkeypatch.setattr("worker.config._ensure_writable", lambda path: False)

    gate = evaluate_startup_gate(bound_config(), "C:")

    assert gate.allowed is False
    assert gate.health == "storage_unavailable"


def test_startup_gate_rejects_low_disk_space(monkeypatch):
    monkeypatch.setattr("worker.config._ensure_writable", lambda path: True)
    monkeypatch.setattr("worker.config._free_bytes", lambda path: 5 * 1024**3 - 1)

    gate = evaluate_startup_gate(bound_config(), "C:")

    assert gate.allowed is False
    assert gate.health == "disk_low"


@pytest.mark.parametrize(
    "missing",
    ["device_no", "school_id", "location_id", "location_name"],
)
def test_startup_gate_requires_complete_device_binding(monkeypatch, missing):
    monkeypatch.setattr("worker.config._ensure_writable", lambda path: True)
    monkeypatch.setattr("worker.config._free_bytes", lambda path: 6 * 1024**3)
    config = bound_config()
    config = WorkerConfig(**{**config.__dict__, missing: None if missing == "school_id" else ""})

    gate = evaluate_startup_gate(config, "C:")

    assert gate.allowed is False
    assert gate.health == "binding_required"


def test_startup_gate_accepts_complete_binding_without_using_network(monkeypatch):
    monkeypatch.setattr("worker.config._ensure_writable", lambda path: True)
    monkeypatch.setattr("worker.config._free_bytes", lambda path: 6 * 1024**3)

    gate = evaluate_startup_gate(bound_config(), "C:")

    assert gate.allowed is True
    assert gate.health == "healthy"
