from __future__ import annotations

import json
import os
import secrets
import socketserver
import threading
from pathlib import Path

from worker.protocol import event, parse_command


class ServerAlreadyRunning(RuntimeError):
    pass


def _private_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(descriptor, content.encode("utf-8"))
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


class _ControlHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        server = self.server.control_server
        self.request.settimeout(server.authentication_timeout)
        try:
            authentication_line = self.rfile.readline(server.max_line_bytes + 1)
            if len(authentication_line) > server.max_line_bytes or not authentication_line.endswith(b"\n"):
                return
            authentication = json.loads(authentication_line)
        except (TimeoutError, OSError):
            return
        except (json.JSONDecodeError, UnicodeDecodeError):
            authentication = {}
        if not secrets.compare_digest(str(authentication.get("token", "")), server.token):
            self._send("error", {"message": "authentication failed"})
            return
        server._add_client(self)
        self.request.settimeout(None)
        try:
            self._send("ready", server.worker.snapshot())
            while True:
                raw_line = self.rfile.readline(server.max_line_bytes + 1)
                if not raw_line:
                    break
                if len(raw_line) > server.max_line_bytes or not raw_line.endswith(b"\n"):
                    break
                try:
                    command = parse_command(raw_line.decode("utf-8"))
                    with server.command_lock:
                        server.worker.handle(command)
                except Exception as exc:
                    self._send("error", {"message": str(exc)})
        except (ConnectionResetError, OSError):
            pass
        finally:
            server._remove_client(self)

    def _send(self, name: str, payload: dict) -> None:
        self.wfile.write((event(name, payload) + "\n").encode("utf-8"))
        self.wfile.flush()


class _ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class InstanceLock:
    def __init__(self, runtime_dir: Path):
        self.runtime_dir = Path(runtime_dir)
        self.path = self.runtime_dir / "worker.lock"
        self.descriptor = None

    def acquire(self):
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(descriptor)
            raise ServerAlreadyRunning("recorder worker is already running") from exc
        os.ftruncate(descriptor, 0)
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        self.descriptor = descriptor
        return self

    def close(self):
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.descriptor = None

    def __enter__(self):
        return self if self.descriptor is not None else self.acquire()

    def __exit__(self, *_args):
        self.close()


class ControlServer:
    def __init__(self, worker, runtime_dir: Path, *, instance_lock=None, authentication_timeout=2.0, max_line_bytes=65536):
        self.worker = worker
        self.runtime_dir = Path(runtime_dir)
        self.endpoint_path = self.runtime_dir / "worker-endpoint.json"
        self.token_path = self.runtime_dir / "worker-token"
        self.token = secrets.token_urlsafe(32)
        self.port = 0
        self.instance_lock = instance_lock
        self._owns_lock = instance_lock is None
        self._server = None
        self._thread = None
        self._clients = set()
        self._clients_lock = threading.Lock()
        self.command_lock = threading.Lock()
        self.authentication_timeout = authentication_timeout
        self.max_line_bytes = max_line_bytes

    def start(self):
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        if self.instance_lock is None:
            self.instance_lock = InstanceLock(self.runtime_dir).acquire()
        try:
            self._server = _ThreadingServer(("127.0.0.1", 0), _ControlHandler)
            self._server.control_server = self
            self.port = self._server.server_address[1]
            _private_write(self.token_path, self.token)
            _private_write(
                self.endpoint_path,
                json.dumps({"host": "127.0.0.1", "port": self.port}),
            )
            self.worker.emit_event = self.broadcast
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            return self
        except Exception:
            self.close()
            raise

    def broadcast(self, name: str, payload: dict) -> None:
        with self._clients_lock:
            clients = list(self._clients)
        for client in clients:
            try:
                client._send(name, payload)
            except OSError:
                self._remove_client(client)

    def _add_client(self, client) -> None:
        with self._clients_lock:
            self._clients.add(client)

    def _remove_client(self, client) -> None:
        with self._clients_lock:
            self._clients.discard(client)

    def close(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
        for path in (self.endpoint_path, self.token_path):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        if self._owns_lock and self.instance_lock is not None:
            self.instance_lock.close()
            self.instance_lock = None

    def __enter__(self):
        return self.start()

    def __exit__(self, _type, _value, _traceback):
        self.close()
