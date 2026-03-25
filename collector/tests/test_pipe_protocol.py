import json
import pytest
from collector.ipc.protocol import (
    CMD_STATUS,
    CMD_SCAN_NOW,
    EVT_STATUS_UPDATE,
    EVT_DETECTION,
    EVT_APPROVAL,
    make_command,
    make_event,
    parse_message,
    MessageError,
)


def test_make_command_status():
    msg = make_command(CMD_STATUS)
    parsed = json.loads(msg)
    assert parsed["type"] == "cmd"
    assert parsed["cmd"] == "status"


def test_make_command_scan_now():
    msg = make_command(CMD_SCAN_NOW)
    parsed = json.loads(msg)
    assert parsed["cmd"] == "scan_now"


def test_make_event_status_update():
    msg = make_event(EVT_STATUS_UPDATE, {
        "connected": True,
        "last_scan": "2026-03-25T12:00:00Z",
        "events_sent": 42,
        "version": "0.5.0",
    })
    parsed = json.loads(msg)
    assert parsed["type"] == "evt"
    assert parsed["evt"] == "status_update"
    assert parsed["data"]["connected"] is True


def test_make_event_detection():
    msg = make_event(EVT_DETECTION, {
        "tool_name": "Claude Code",
        "decision_state": "detect",
        "confidence": 0.87,
    })
    parsed = json.loads(msg)
    assert parsed["evt"] == "detection"
    assert parsed["data"]["tool_name"] == "Claude Code"


def test_make_event_approval():
    msg = make_event(EVT_APPROVAL, {
        "tool_name": "Claude Code",
        "status": "approved",
    })
    parsed = json.loads(msg)
    assert parsed["evt"] == "approval"


def test_parse_message_valid_command():
    raw = json.dumps({"type": "cmd", "cmd": "status"})
    msg = parse_message(raw)
    assert msg["type"] == "cmd"
    assert msg["cmd"] == "status"


def test_parse_message_valid_event():
    raw = json.dumps({"type": "evt", "evt": "detection", "data": {"tool_name": "Cursor"}})
    msg = parse_message(raw)
    assert msg["type"] == "evt"


def test_parse_message_invalid_json():
    with pytest.raises(MessageError):
        parse_message("not json")


def test_parse_message_missing_type():
    with pytest.raises(MessageError):
        parse_message(json.dumps({"cmd": "status"}))


def test_parse_message_unknown_type():
    with pytest.raises(MessageError):
        parse_message(json.dumps({"type": "unknown"}))
