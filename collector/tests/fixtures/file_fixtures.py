"""Helpers that create realistic file-system footprints in a temp directory.

Each ``create_*_footprint`` function accepts a ``home`` Path (the temp directory
standing in for ``Path.home()``) and populates it with the exact file/dir layout
the corresponding scanner checks.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Aider
# ---------------------------------------------------------------------------

def create_aider_footprint(
    home: Path,
    *,
    with_artifacts: bool = True,
    with_cache_dir: bool = True,
    recent: bool = True,
) -> Path:
    """Create Aider file-layer artifacts under *home*.

    Returns the repo path that contains .aider* files.
    """
    repo = home / "Documents" / "test-repo"
    (repo / ".git").mkdir(parents=True)

    if with_artifacts:
        for name in (".aider.conf.yml", ".aider.chat.history.md", ".aider.input.history"):
            artifact = repo / name
            artifact.write_text(f"# {name}\n")
            if recent:
                os.utime(artifact, (time.time(), time.time()))
            else:
                os.utime(artifact, (time.time() - 200_000, time.time() - 200_000))

    if with_cache_dir:
        cache = home / ".aider"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "cache.json").write_text("{}")

    return repo


# ---------------------------------------------------------------------------
# LM Studio
# ---------------------------------------------------------------------------

def create_lm_studio_footprint(
    home: Path,
    *,
    with_app: bool = True,
    with_models: bool = True,
    app_path: Path | None = None,
) -> Path:
    """Create LM Studio file-layer artifacts.

    Returns the app support directory path.
    """
    app_support = home / "Library" / "Application Support" / "LM Studio"
    app_support.mkdir(parents=True, exist_ok=True)

    version_file = app_support / "version.json"
    version_file.write_text(json.dumps({"version": "0.3.5"}))

    settings = app_support / "User"
    settings.mkdir(parents=True, exist_ok=True)

    model_dir = home / ".lmstudio" / "models"
    model_path_str = str(model_dir)

    (settings / "settings.json").write_text(json.dumps({
        "modelPath": model_path_str,
    }))

    if with_app and app_path is not None:
        contents = app_path / "Contents"
        contents.mkdir(parents=True, exist_ok=True)

    if with_models:
        model_dir.mkdir(parents=True, exist_ok=True)
        dummy_model = model_dir / "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
        dummy_model.write_bytes(b"\x00" * 4096)

    return app_support


# ---------------------------------------------------------------------------
# Continue
# ---------------------------------------------------------------------------

def create_continue_footprint(
    home: Path,
    *,
    backends: list[str] | None = None,
    with_extension: bool = True,
    with_global_storage: bool = True,
    recent_files: bool = True,
) -> Path:
    """Create Continue extension file-layer artifacts.

    *backends* controls the ``models[].provider`` values written to config.json.
    Defaults to ``["anthropic"]`` (approved).
    """
    if backends is None:
        backends = ["anthropic"]

    continue_dir = home / ".continue"
    continue_dir.mkdir(parents=True, exist_ok=True)

    config = {
        "models": [{"provider": b, "model": "default"} for b in backends],
        "tabAutocompleteModel": {"provider": backends[0]} if backends else None,
    }
    config_path = continue_dir / "config.json"
    config_path.write_text(json.dumps(config))
    if recent_files:
        os.utime(config_path, (time.time(), time.time()))

    if with_extension:
        ext_dir = home / ".cursor" / "extensions" / "continue.continue-0.9.1"
        ext_dir.mkdir(parents=True, exist_ok=True)
        (ext_dir / "package.json").write_text(json.dumps({
            "name": "continue",
            "version": "0.9.1",
            "publisher": "Continue",
        }))

    if with_global_storage:
        storage = (
            home / "Library" / "Application Support" / "Cursor"
            / "User" / "globalStorage" / "continue.continue"
        )
        storage.mkdir(parents=True, exist_ok=True)
        (storage / "state.json").write_text("{}")

    return continue_dir


# ---------------------------------------------------------------------------
# GPT-Pilot
# ---------------------------------------------------------------------------

def create_gpt_pilot_footprint(
    home: Path,
    *,
    with_state_dir: bool = True,
    with_workspace: bool = True,
    file_churn: int = 0,
) -> Path:
    """Create GPT-Pilot file-layer artifacts.

    *file_churn* controls how many recently-modified files to create in the
    workspace directory (triggers high-file-churn detection when > 20).
    """
    workspace = home / "Documents" / "pilot-project"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / ".git").mkdir(exist_ok=True)

    if with_state_dir:
        state = workspace / ".gpt-pilot"
        state.mkdir(parents=True, exist_ok=True)
        (state / "project.json").write_text(json.dumps({"name": "test-app"}))
        (state / "steps.json").write_text("[]")
        (state / "llm_requests.log").write_text("")

    if with_workspace:
        ws = home / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        project = ws / "generated-app"
        project.mkdir(exist_ok=True)
        now = time.time()
        for i in range(file_churn):
            f = project / f"file_{i:03d}.py"
            f.write_text(f"# generated file {i}\n")
            os.utime(f, (now, now))

    return workspace


# ---------------------------------------------------------------------------
# Cline
# ---------------------------------------------------------------------------

def create_cline_footprint(
    home: Path,
    *,
    with_extension: bool = True,
    with_tasks: bool = False,
    tool_calls: bool = False,
    write_ops: bool = False,
    task_count: int = 3,
) -> Path:
    """Create Cline extension file-layer artifacts.

    When *tool_calls* is True the most recent task's ``ui_messages.json``
    contains ``tool_use`` entries (triggers Class C).
    When *write_ops* is True it also contains ``write_to_file`` entries
    (triggers Class C with R3 risk).
    """
    if with_extension:
        ext_dir = (
            home / "Library" / "Application Support" / "Cursor"
            / "User" / "extensions" / "saoudrizwan.claude-dev-3.2.1"
        )
        ext_dir.mkdir(parents=True, exist_ok=True)
        (ext_dir / "package.json").write_text(json.dumps({
            "name": "claude-dev",
            "version": "3.2.1",
            "publisher": "saoudrizwan",
        }))

    storage = (
        home / "Library" / "Application Support" / "Cursor"
        / "User" / "globalStorage" / "saoudrizwan.claude-dev"
    )

    if with_tasks:
        tasks_dir = storage / "tasks"
        now = time.time()
        for i in range(task_count):
            task = tasks_dir / f"task-{i:04d}"
            task.mkdir(parents=True, exist_ok=True)
            os.utime(task, (now - i * 600, now - i * 600))

        latest = tasks_dir / "task-0000"
        messages: list[dict] = [
            {"type": "say", "text": "Hello"},
            {"type": "say", "text": "Working on it..."},
        ]
        if tool_calls:
            messages.extend([
                {"type": "tool_use", "name": "read_file", "input": {"path": "main.py"}},
                {"type": "tool_use", "name": "list_files", "input": {"path": "."}},
                {"type": "ask", "text": "May I edit this file?"},
            ])
        if write_ops:
            messages.extend([
                {"type": "write_to_file", "path": "app.py", "content": "print('hi')"},
                {"type": "execute_command", "command": "python app.py"},
            ])

        (latest / "ui_messages.json").write_text(json.dumps(messages))

        api_log = storage / "api_conversation_history.json"
        api_log.parent.mkdir(parents=True, exist_ok=True)
        api_log.write_text(json.dumps([{"role": "user", "content": f"msg {i}"} for i in range(15)]))

    return storage
