"""Message protocol for the DetecAgent named pipe.

Wire format: newline-delimited JSON (one message per line).

Commands (tray → service):
    {"type": "cmd", "cmd": "status"}
    {"type": "cmd", "cmd": "scan_now"}

Events (service → tray):
    {"type": "evt", "evt": "status_update", "data": {...}}
    {"type": "evt", "evt": "detection",     "data": {...}}
    {"type": "evt", "evt": "approval",      "data": {...}}
"""

import json

PIPE_NAME = r"\\.\pipe\DetecAgent"

CMD_STATUS = "status"
CMD_SCAN_NOW = "scan_now"
VALID_COMMANDS = {CMD_STATUS, CMD_SCAN_NOW}

EVT_STATUS_UPDATE = "status_update"
EVT_DETECTION = "detection"
EVT_APPROVAL = "approval"
VALID_EVENTS = {EVT_STATUS_UPDATE, EVT_DETECTION, EVT_APPROVAL}


class MessageError(Exception):
    pass


def make_command(cmd: str) -> str:
    if cmd not in VALID_COMMANDS:
        raise MessageError(f"Unknown command: {cmd}")
    return json.dumps({"type": "cmd", "cmd": cmd})


def make_event(evt: str, data: dict) -> str:
    if evt not in VALID_EVENTS:
        raise MessageError(f"Unknown event: {evt}")
    return json.dumps({"type": "evt", "evt": evt, "data": data})


def parse_message(raw: str) -> dict:
    try:
        msg = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise MessageError(f"Invalid JSON: {exc}") from exc

    if "type" not in msg:
        raise MessageError("Missing 'type' field")

    if msg["type"] == "cmd":
        if msg.get("cmd") not in VALID_COMMANDS:
            raise MessageError(f"Unknown command: {msg.get('cmd')}")
    elif msg["type"] == "evt":
        if msg.get("evt") not in VALID_EVENTS:
            raise MessageError(f"Unknown event: {msg.get('evt')}")
    else:
        raise MessageError(f"Unknown type: {msg['type']}")

    return msg
