"""Canned subprocess responses for scanner integration tests.

Each response set is a dict keyed by a tuple representing the command prefix.
Values are (returncode, stdout) pairs used to build CompletedProcess objects.
"""

from __future__ import annotations

import subprocess
from typing import Any

CompletedLike = subprocess.CompletedProcess[str]


def _cp(rc: int, stdout: str) -> CompletedLike:
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr="")


EMPTY = _cp(1, "")

# ---------------------------------------------------------------------------
# Aider
# ---------------------------------------------------------------------------

AIDER_RUNNING: dict[tuple[str, ...], CompletedLike] = {
    ("pgrep", "-fl", "aider"): _cp(0, "12345 python /usr/local/bin/aider --model gpt-4o test.py\n"),
    ("ps", "-p", "12345", "-o", "pid,ppid,user,command"): _cp(
        0,
        "  PID  PPID USER            COMMAND\n"
        "12345 12300 testuser        python /usr/local/bin/aider --model gpt-4o test.py\n",
    ),
    ("pgrep", "-P", "12345"): _cp(0, "12346\n12347\n"),
    ("ps", "-p", "12346", "-o", "pid,command"): _cp(0, "  PID COMMAND\n12346 git commit -m aider: fix tests\n"),
    ("ps", "-p", "12347", "-o", "pid,command"): _cp(0, "  PID COMMAND\n12347 python -m pytest\n"),
    ("pip", "show", "aider-chat"): _cp(
        0,
        "Name: aider-chat\nVersion: 0.42.0\nLocation: /usr/local/lib/python3.12/site-packages\n",
    ),
    ("aider", "--version"): _cp(0, "aider 0.42.0\n"),
    ("lsof", "-i", "-n", "-P"): _cp(
        0,
        "COMMAND   PID     USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\n"
        "python  12345 testuser   8u  IPv4 0x1234      0t0  TCP 192.168.1.10:54321->104.18.7.23:443 (ESTABLISHED)\n",
    ),
    ("git", "config", "--global", "user.email"): _cp(0, "dev@example.com\n"),
}

AIDER_GIT_LOG_MATCH = _cp(0, "aider: fix input validation\nfeat: add user model\n")
AIDER_GIT_LOG_EMPTY = _cp(0, "feat: add user model\nfix: typo in readme\n")

# ---------------------------------------------------------------------------
# LM Studio
# ---------------------------------------------------------------------------

LM_STUDIO_RUNNING: dict[tuple[str, ...], CompletedLike] = {
    ("pgrep", "-fl", "LM Studio"): _cp(
        0,
        '55001 /Applications/LM Studio.app/Contents/MacOS/LM Studio --type=renderer\n',
    ),
    ("pgrep", "-fl", "lm-studio"): EMPTY,
    ("pgrep", "-fl", "lmstudio"): EMPTY,
    ("ps", "-p", "55001", "-o", "pid,ppid,user,command"): _cp(
        0,
        "  PID  PPID USER            COMMAND\n"
        "55001 55000 testuser        /Applications/LM Studio.app/Contents/MacOS/LM Studio --type=renderer\n",
    ),
    ("lsof", "-i", ":1234", "-n", "-P"): _cp(
        0,
        "COMMAND   PID     USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\n"
        "node    55002 testuser   22u  IPv4 0xabcd      0t0  TCP *:1234 (LISTEN)\n",
    ),
    ("lsof", "-i", "-n", "-P"): _cp(0, ""),
    ("git", "config", "--global", "user.email"): _cp(0, "dev@example.com\n"),
}

LM_STUDIO_NOT_RUNNING: dict[tuple[str, ...], CompletedLike] = {
    ("pgrep", "-fl", "LM Studio"): EMPTY,
    ("pgrep", "-fl", "lm-studio"): EMPTY,
    ("pgrep", "-fl", "lmstudio"): EMPTY,
    ("lsof", "-i", ":1234", "-n", "-P"): EMPTY,
    ("lsof", "-i", "-n", "-P"): EMPTY,
    ("git", "config", "--global", "user.email"): _cp(0, "dev@example.com\n"),
}

# ---------------------------------------------------------------------------
# Continue
# ---------------------------------------------------------------------------

CONTINUE_ACTIVE: dict[tuple[str, ...], CompletedLike] = {
    ("pgrep", "-fl", "Code"): EMPTY,
    ("pgrep", "-fl", "Cursor"): _cp(
        0,
        "60001 /Applications/Cursor.app/Contents/MacOS/Cursor\n"
        "60010 /Applications/Cursor.app/Contents/Frameworks/Cursor Helper (Renderer).app --extensionHost\n",
    ),
    ("lsof", "-i", "-n", "-P"): _cp(
        0,
        "COMMAND   PID     USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\n"
        "Cursor  60010 testuser   15u  IPv4 0x5678      0t0  TCP 127.0.0.1:54100->127.0.0.1:11434 (ESTABLISHED)\n",
    ),
    ("git", "config", "--global", "user.email"): _cp(0, "dev@example.com\n"),
}

CONTINUE_APPROVED_ACTIVE: dict[tuple[str, ...], CompletedLike] = {
    ("pgrep", "-fl", "Code"): EMPTY,
    ("pgrep", "-fl", "Cursor"): _cp(
        0,
        "60001 /Applications/Cursor.app/Contents/MacOS/Cursor\n"
        "60010 /Applications/Cursor.app/Contents/Frameworks/Cursor Helper (Renderer).app --extensionHost\n",
    ),
    ("lsof", "-i", "-n", "-P"): _cp(
        0,
        "COMMAND   PID     USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\n"
        "Cursor  60010 testuser   15u  IPv4 0x5678      0t0  TCP 192.168.1.10:54100->104.18.7.23:443 (ESTABLISHED)\n",
    ),
    ("git", "config", "--global", "user.email"): _cp(0, "dev@example.com\n"),
}

CONTINUE_NOT_RUNNING: dict[tuple[str, ...], CompletedLike] = {
    ("pgrep", "-fl", "Code"): EMPTY,
    ("pgrep", "-fl", "Cursor"): EMPTY,
    ("lsof", "-i", "-n", "-P"): EMPTY,
    ("git", "config", "--global", "user.email"): _cp(0, "dev@example.com\n"),
}

# ---------------------------------------------------------------------------
# GPT-Pilot
# ---------------------------------------------------------------------------

GPT_PILOT_RUNNING: dict[tuple[str, ...], CompletedLike] = {
    ("pgrep", "-fl", "gpt-pilot"): _cp(0, "70001 python -m gpt_pilot\n"),
    ("pgrep", "-fl", "gpt_pilot"): EMPTY,
    ("pgrep", "-fl", "pythagora"): EMPTY,
    ("ps", "-p", "70001", "-o", "pid,ppid,user,command"): _cp(
        0,
        "  PID  PPID USER            COMMAND\n"
        "70001 70000 testuser        python -m gpt_pilot\n",
    ),
    ("pgrep", "-P", "70001"): _cp(0, "70002\n70003\n"),
    ("ps", "-p", "70002", "-o", "pid,command"): _cp(0, "  PID COMMAND\n70002 node server.js\n"),
    ("ps", "-p", "70003", "-o", "pid,command"): _cp(0, "  PID COMMAND\n70003 python manage.py runserver\n"),
    ("pip", "show", "gpt-pilot"): _cp(
        0,
        "Name: gpt-pilot\nVersion: 0.2.5\nLocation: /usr/local/lib/python3.12/site-packages\n",
    ),
    ("pip", "show", "pythagora"): EMPTY,
    ("pip", "show", "gpt_pilot"): EMPTY,
    ("lsof", "-i", "-n", "-P"): _cp(
        0,
        "COMMAND   PID     USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\n"
        "python  70001 testuser   9u  IPv4 0xdead      0t0  TCP 192.168.1.10:55432->104.18.7.23:443 (ESTABLISHED)\n",
    ),
    ("git", "config", "--global", "user.email"): _cp(0, "dev@example.com\n"),
}

GPT_PILOT_NOT_RUNNING: dict[tuple[str, ...], CompletedLike] = {
    ("pgrep", "-fl", "gpt-pilot"): EMPTY,
    ("pgrep", "-fl", "gpt_pilot"): EMPTY,
    ("pgrep", "-fl", "pythagora"): EMPTY,
    ("pip", "show", "gpt-pilot"): EMPTY,
    ("pip", "show", "pythagora"): EMPTY,
    ("pip", "show", "gpt_pilot"): EMPTY,
    ("lsof", "-i", "-n", "-P"): EMPTY,
    ("git", "config", "--global", "user.email"): _cp(0, "dev@example.com\n"),
}

# ---------------------------------------------------------------------------
# Cline
# ---------------------------------------------------------------------------

CLINE_ACTIVE: dict[tuple[str, ...], CompletedLike] = {
    ("pgrep", "-fl", "Code"): EMPTY,
    ("pgrep", "-fl", "Cursor"): _cp(
        0,
        "80001 /Applications/Cursor.app/Contents/MacOS/Cursor\n"
        "80010 /Applications/Cursor.app/Contents/Frameworks/Cursor Helper (Renderer).app --extensionHost\n",
    ),
    ("lsof", "-i", "-n", "-P"): _cp(
        0,
        "COMMAND   PID     USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\n"
        "Cursor  80010 testuser   12u  IPv4 0x9999      0t0  TCP 192.168.1.10:55000->104.18.7.23:443 (ESTABLISHED)\n",
    ),
    ("git", "config", "--global", "user.email"): _cp(0, "dev@example.com\n"),
}

CLINE_NOT_RUNNING: dict[tuple[str, ...], CompletedLike] = {
    ("pgrep", "-fl", "Code"): EMPTY,
    ("pgrep", "-fl", "Cursor"): EMPTY,
    ("lsof", "-i", "-n", "-P"): EMPTY,
    ("git", "config", "--global", "user.email"): _cp(0, "dev@example.com\n"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_dispatcher(
    responses: dict[tuple[str, ...], CompletedLike],
    fallback: CompletedLike | None = None,
) -> Any:
    """Return a callable that dispatches _run_cmd args to canned responses.

    Matches the longest prefix first so both ``("pgrep", "-fl", "aider")`` and
    ``("pgrep", "-P", "12345")`` can coexist.
    """
    if fallback is None:
        fallback = EMPTY

    def _dispatch(self_scanner: Any, args: list[str], **kwargs: Any) -> CompletedLike:
        key = tuple(args)
        if key in responses:
            return responses[key]
        for length in range(len(args), 0, -1):
            prefix = tuple(args[:length])
            if prefix in responses:
                return responses[prefix]
        return fallback

    return _dispatch
