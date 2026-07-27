import pytest

from worker.protocol import parse_command


def test_parse_start_command():
    assert parse_command('{"id":"1","command":"start","payload":{}}').command == "start"


def test_reject_unknown_command():
    with pytest.raises(ValueError, match="unsupported command"):
        parse_command('{"id":"1","command":"format_disk","payload":{}}')


@pytest.mark.parametrize("name", ["flush_queue", "update_settings", "apply_binding"])
def test_parse_runtime_control_commands(name):
    parsed = parse_command(f'{{"id":"1","command":"{name}","payload":{{}}}}')
    assert parsed.command == name
