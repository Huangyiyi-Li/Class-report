from pathlib import Path

import pytest

from worker.config import (
    WorkerConfig,
    evaluate_startup_gate,
    validate_binding_payload,
    validate_data_root,
    validate_settings_patch,
)


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
    with pytest.raises(ValueError, match="本地绝对路径"):
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


def test_save_atomic_round_trips_binding_metadata(tmp_path: Path):
    path = tmp_path / "worker-config.json"
    config = WorkerConfig(
        data_root="D:/Recorder",
        device_no="AABBCCDDEEFF",
        school_id=1001,
        school_name="星河实验学校",
        location_type="classroom",
        location_id="room-101",
        location_name="一年级一班教室",
        class_id="class-101",
        class_name="一年级一班",
        binding_source="mock",
        bound_at="2026-07-15T08:00:00.000Z",
    )

    config.save_atomic(path)

    assert WorkerConfig.load(path) == config


def classroom_binding():
    return {
        "deviceNo": "AABBCCDDEEFF",
        "schoolId": 1001,
        "schoolName": "星河实验学校",
        "locationType": "classroom",
        "locationId": "room-101",
        "locationName": "一年级一班教室",
        "classId": "class-101",
        "className": "一年级一班",
        "bindingSource": "mock",
        "boundAt": "2026-07-15T08:00:00.000Z",
    }


def test_validate_classroom_binding_maps_to_worker_config_fields():
    payload = classroom_binding()

    result = validate_binding_payload(payload)

    assert result == {
        "device_no": "AABBCCDDEEFF",
        "school_id": 1001,
        "school_name": "星河实验学校",
        "location_type": "classroom",
        "location_id": "room-101",
        "location_name": "一年级一班教室",
        "class_id": "class-101",
        "class_name": "一年级一班",
        "binding_source": "mock",
        "bound_at": "2026-07-15T08:00:00.000Z",
    }
    assert payload == classroom_binding()


def test_validate_studio_binding_requires_empty_class_fields():
    payload = classroom_binding() | {
        "locationType": "studio",
        "locationId": "studio-main",
        "locationName": "公共录播教室",
        "classId": "",
        "className": "",
    }

    result = validate_binding_payload(payload)

    assert result["class_id"] == ""
    assert result["class_name"] == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("deviceNo", ""),
        ("schoolId", True),
        ("schoolName", 123),
        ("locationType", "office"),
        ("locationId", "bad\nvalue"),
        ("locationName", ""),
        ("classId", ""),
        ("className", ""),
        ("bindingSource", "fallback"),
        ("boundAt", "15 July"),
    ],
)
def test_validate_classroom_binding_rejects_invalid_fields(field, value):
    payload = classroom_binding() | {field: value}

    with pytest.raises(ValueError):
        validate_binding_payload(payload)


@pytest.mark.parametrize("class_field", ["classId", "className"])
def test_validate_studio_binding_rejects_nonempty_class_fields(class_field):
    payload = classroom_binding() | {
        "locationType": "studio",
        "classId": "",
        "className": "",
        class_field: "stale-class",
    }

    with pytest.raises(ValueError):
        validate_binding_payload(payload)


def test_validate_binding_rejects_missing_and_unknown_fields():
    missing = classroom_binding()
    missing.pop("locationId")
    with pytest.raises(ValueError):
        validate_binding_payload(missing)

    with pytest.raises(ValueError):
        validate_binding_payload(classroom_binding() | {"baseUrl": "https://evil.invalid"})


def test_worker_validates_core_settings_patch_strictly():
    assert validate_settings_patch({"autoRecordEnabled": True, "inputDevice": " mic-2 "}) == {
        "auto_record_enabled": True,
        "input_device": "mic-2",
    }


def test_worker_validates_safe_windows_data_root_in_patch():
    assert validate_settings_patch({"dataRoot": "D:/Recorder"}, system_drive="C:") == {
        "data_root": "D:/Recorder",
    }


@pytest.mark.parametrize("data_root", ["relative", "C:/Recorder", "c:\\Recorder", "\\\\server\\share\\Recorder"])
def test_worker_rejects_unsafe_windows_data_root_in_patch(data_root):
    with pytest.raises(ValueError):
        validate_settings_patch({"dataRoot": data_root}, system_drive="C:")


@pytest.mark.parametrize("patch", [
    None, [], {"autoRecordEnabled": "true"}, {"inputDevice": {}},
    {"inputDevice": "x" * 257}, {"deviceNo": "attacker"},
    {"schoolId": 1}, {"locationId": "other"}, {"baseUrl": "https://evil.invalid"},
])
def test_worker_rejects_invalid_or_binding_settings_patch(patch):
    with pytest.raises(ValueError):
        validate_settings_patch(patch)


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
