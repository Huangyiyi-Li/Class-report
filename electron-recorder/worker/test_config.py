from pathlib import Path

import pytest

from worker.config import WorkerConfig, validate_data_root


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
