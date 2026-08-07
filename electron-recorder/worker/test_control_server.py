from __future__ import annotations

import json
import os
import socket
import threading
import time

import pytest

from worker.control_server import ControlServer, ServerAlreadyRunning
from worker.protocol import Command


class FakeWorker:
    def __init__(self):
        self.commands = []
        self.emit_event = lambda _name, _payload: None
        self.state = {"recording": "idle", "upload": "clear", "health": "healthy"}

    def snapshot(self):
        return dict(self.state)

    def handle(self, command: Command):
        self.commands.append(command.command)
        if command.command == "start":
            self.state["recording"] = "recording"
        elif command.command == "pause":
            self.state["recording"] = "paused"
        elif command.command == "stop":
            self.state["recording"] = "idle"
        self.emit_event("snapshot", self.snapshot())
        return True


def connect(server, token):
    sock = socket.create_connection(("127.0.0.1", server.port), timeout=1)
    stream = sock.makefile("rwb")
    stream.write((json.dumps({"token": token}) + "\n").encode())
    stream.flush()
    return sock, stream


def read_message(stream):
    return json.loads(stream.readline())


def test_authenticated_client_can_command_worker(tmp_path):
    worker = FakeWorker()
    with ControlServer(worker, tmp_path) as server:
        sock, stream = connect(server, server.token)
        assert read_message(stream)["event"] == "ready"
        stream.write(b'{"id":"1","command":"start","payload":{}}\n')
        stream.flush()
        message = read_message(stream)
        assert message["event"] == "snapshot"
        assert message["payload"]["recording"] == "recording"
        result = read_message(stream)
        assert result == {"event": "command_result", "payload": {"id": "1", "success": True}}
        assert worker.commands == ["start"]
        sock.close()


def test_command_result_can_return_data_to_electron(tmp_path):
    class ResultWorker(FakeWorker):
        def execute_command(self, command):
            self.commands.append(command.command)
            return {"devices": [{"value": "Microphone 1", "label": "Microphone 1"}]}

    worker = ResultWorker()
    with ControlServer(worker, tmp_path) as server:
        sock, stream = connect(server, server.token)
        read_message(stream)
        stream.write(b'{"id":"devices","command":"snapshot","payload":{}}\n')
        stream.flush()

        result = read_message(stream)

        assert result["payload"]["result"] == {
            "devices": [{"value": "Microphone 1", "label": "Microphone 1"}]
        }
        sock.close()


def test_wrong_token_is_rejected(tmp_path):
    worker = FakeWorker()
    with ControlServer(worker, tmp_path) as server:
        sock, stream = connect(server, "wrong-token")
        assert read_message(stream)["event"] == "error"
        assert stream.readline() == b""
        assert worker.commands == []
        sock.close()


def test_disconnected_client_does_not_stop_capture(tmp_path):
    worker = FakeWorker()
    with ControlServer(worker, tmp_path) as server:
        sock, stream = connect(server, server.token)
        read_message(stream)
        stream.write(b'{"id":"1","command":"start","payload":{}}\n')
        stream.flush()
        read_message(stream)
        sock.close()
        time.sleep(0.05)
        assert worker.state["recording"] == "recording"
        assert worker.commands == ["start"]

        second, second_stream = connect(server, server.token)
        ready = read_message(second_stream)
        assert ready["payload"]["recording"] == "recording"
        second.close()


def test_second_server_instance_is_rejected(tmp_path):
    with ControlServer(FakeWorker(), tmp_path):
        with pytest.raises(ServerAlreadyRunning):
            ControlServer(FakeWorker(), tmp_path).start()


def test_endpoint_is_loopback_and_secret_files_are_owner_restricted(tmp_path):
    with ControlServer(FakeWorker(), tmp_path) as server:
        endpoint = json.loads((tmp_path / "worker-endpoint.json").read_text())
        assert endpoint == {"host": "127.0.0.1", "port": server.port}
        assert (tmp_path / "worker-token").read_text() == server.token
        if os.name != "nt":
            assert (tmp_path / "worker-token").stat().st_mode & 0o077 == 0
            assert (tmp_path / "worker-endpoint.json").stat().st_mode & 0o077 == 0


def test_commands_from_multiple_clients_are_serialized(tmp_path):
    active = 0
    overlap = []
    worker = FakeWorker()
    original_handle = worker.handle

    def guarded_handle(command):
        nonlocal active
        active += 1
        if active > 1:
            overlap.append(command.command)
        time.sleep(0.02)
        try:
            return original_handle(command)
        finally:
            active -= 1

    worker.handle = guarded_handle
    with ControlServer(worker, tmp_path) as server:
        clients = [connect(server, server.token) for _ in range(3)]
        for _, stream in clients:
            read_message(stream)
        commands = ["start", "stop", "update_settings"]
        threads = []
        for (_, stream), command in zip(clients, commands):
            thread = threading.Thread(
                target=lambda s=stream, c=command: (
                    s.write((json.dumps({"id": c, "command": c, "payload": {}}) + "\n").encode()),
                    s.flush(),
                )
            )
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        time.sleep(0.1)
        assert overlap == []
        for sock, _ in clients:
            sock.close()


def test_authentication_times_out_and_oversized_lines_are_closed(tmp_path):
    with ControlServer(FakeWorker(), tmp_path, authentication_timeout=0.05, max_line_bytes=128) as server:
        idle = socket.create_connection(("127.0.0.1", server.port), timeout=1)
        idle.settimeout(0.3)
        assert idle.recv(1) == b""
        idle.close()

        sock, stream = connect(server, server.token)
        read_message(stream)
        stream.write(b"{" + b"x" * 200 + b"}\n")
        stream.flush()
        assert stream.readline() == b""
        sock.close()
