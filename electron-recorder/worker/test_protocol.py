import pytest

from worker.protocol import parse_command


def test_parse_start_command():
    assert parse_command('{"id":"1","command":"start","payload":{}}').command == "start"


def test_reject_unknown_command():
    with pytest.raises(ValueError, match="unsupported command"):
        parse_command('{"id":"1","command":"format_disk","payload":{}}')
