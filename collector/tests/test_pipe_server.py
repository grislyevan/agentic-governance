import json
import threading
import pytest
from unittest.mock import MagicMock
from collector.ipc.protocol import (
    CMD_STATUS,
    CMD_SCAN_NOW,
    EVT_STATUS_UPDATE,
    EVT_DETECTION,
    make_command,
    make_event,
)
from collector.ipc.pipe_server import PipeServer


class FakePipe:
    """In-memory pipe for testing without win32pipe."""

    def __init__(self):
        self.inbox = []
        self.outbox = []
        self.closed = False

    def read_line(self):
        if not self.inbox:
            return None
        return self.inbox.pop(0)

    def write_line(self, line):
        self.outbox.append(line)

    def close(self):
        self.closed = True


def test_server_handles_status_command():
    pipe = FakePipe()
    status_data = {"connected": True, "last_scan": None, "events_sent": 0, "version": "0.5.0"}
    server = PipeServer(status_provider=lambda: status_data)
    pipe.inbox.append(make_command(CMD_STATUS))

    server._handle_message(pipe, pipe.inbox.pop(0))

    assert len(pipe.outbox) == 1
    msg = json.loads(pipe.outbox[0])
    assert msg["evt"] == "status_update"
    assert msg["data"]["connected"] is True


def test_server_handles_scan_now_command():
    scan_callback = MagicMock()
    server = PipeServer(status_provider=lambda: {}, scan_callback=scan_callback)
    pipe = FakePipe()

    server._handle_message(pipe, make_command(CMD_SCAN_NOW))

    scan_callback.assert_called_once()


def test_server_broadcast_event():
    server = PipeServer(status_provider=lambda: {})
    pipe = FakePipe()
    server._clients = [pipe]

    event_msg = make_event(EVT_DETECTION, {"tool_name": "Cursor", "decision_state": "warn"})
    server.broadcast(event_msg)

    assert len(pipe.outbox) == 1
    msg = json.loads(pipe.outbox[0])
    assert msg["evt"] == "detection"


def test_server_broadcast_skips_closed_clients():
    server = PipeServer(status_provider=lambda: {})
    alive = FakePipe()
    dead = FakePipe()
    dead.closed = True
    server._clients = [alive, dead]

    server.broadcast(make_event(EVT_STATUS_UPDATE, {"connected": True}))

    assert len(alive.outbox) == 1
    assert len(dead.outbox) == 0


def test_server_ignores_invalid_message():
    server = PipeServer(status_provider=lambda: {})
    pipe = FakePipe()

    # Should not raise
    server._handle_message(pipe, "not valid json")
    assert len(pipe.outbox) == 0
