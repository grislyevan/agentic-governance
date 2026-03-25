import json
import pytest
from unittest.mock import MagicMock, patch
from collector.ipc.protocol import CMD_STATUS, CMD_SCAN_NOW, EVT_STATUS_UPDATE, make_event
from collector.ipc.pipe_client import PipeClient


class FakePipeHandle:
    def __init__(self):
        self.written = []
        self.to_read = []
        self.closed = False

    def write(self, data):
        self.written.append(data)

    def read(self):
        if self.to_read:
            return (0, self.to_read.pop(0).encode("utf-8"))
        raise Exception("No data")


def test_client_send_status_command():
    client = PipeClient()
    client._handle = FakePipeHandle()
    client._connected = True

    client.send_command(CMD_STATUS)

    written = client._handle.written[0].decode("utf-8").strip()
    msg = json.loads(written)
    assert msg["cmd"] == "status"


def test_client_send_scan_now_command():
    client = PipeClient()
    client._handle = FakePipeHandle()
    client._connected = True

    client.send_command(CMD_SCAN_NOW)

    written = client._handle.written[0].decode("utf-8").strip()
    msg = json.loads(written)
    assert msg["cmd"] == "scan_now"


def test_client_on_event_callback():
    callback = MagicMock()
    client = PipeClient()
    client.on_event = callback

    event = make_event(EVT_STATUS_UPDATE, {"connected": True})
    client._dispatch(event)

    callback.assert_called_once()
    args = callback.call_args[0][0]
    assert args["evt"] == "status_update"


def test_client_not_connected():
    client = PipeClient()
    assert client.connected is False


def test_client_dispatch_ignores_invalid():
    callback = MagicMock()
    client = PipeClient()
    client.on_event = callback

    client._dispatch("not json")
    callback.assert_not_called()
