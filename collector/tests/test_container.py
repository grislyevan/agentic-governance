"""Tests for container and remote-dev detection (engine.container)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

_COLLECTOR_DIR = str(Path(__file__).resolve().parent.parent)
if _COLLECTOR_DIR not in sys.path:
    sys.path.insert(0, _COLLECTOR_DIR)

from engine.container import (
    is_containerized,
    is_child_of_docker,
    is_devcontainer,
    is_remote_dev_context,
)


class TestIsContainerized:
    """is_containerized is tested indirectly via policy tests; basic smoke here."""

    def test_returns_bool(self) -> None:
        assert isinstance(is_containerized(None), bool)


class TestIsChildOfDocker:
    def test_returns_bool(self) -> None:
        assert isinstance(is_child_of_docker(os.getpid()), bool)


class TestIsDevcontainer:
    def test_no_env_returns_false(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in ("DEVCONTAINER", "DEVCONTAINER_ID"):
                os.environ.pop(k, None)
            assert is_devcontainer() is False

    def test_devcontainer_env_true(self) -> None:
        with mock.patch.dict(os.environ, {"DEVCONTAINER": "1"}):
            assert is_devcontainer() is True

    def test_devcontainer_id_set(self) -> None:
        with mock.patch.dict(os.environ, {"DEVCONTAINER_ID": "my-container"}):
            assert is_devcontainer() is True

    def test_devcontainer_zero_returns_false(self) -> None:
        with mock.patch.dict(os.environ, {"DEVCONTAINER": "0"}):
            assert is_devcontainer() is False

    def test_different_pid_returns_false(self) -> None:
        """When pid is not current process we do not read other process env."""
        with mock.patch.dict(os.environ, {"DEVCONTAINER": "1"}):
            assert is_devcontainer(pid=99999) is False


class TestIsRemoteDevContext:
    def test_no_env_returns_false(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            for k in ("VSCODE_IPC_HOOK_CLI", "REMOTE_CONTAINERS", "CODESPACES", "SSH_CONNECTION"):
                os.environ.pop(k, None)
            assert is_remote_dev_context() is False

    def test_vscode_ipc_hook_returns_true(self) -> None:
        with mock.patch.dict(os.environ, {"VSCODE_IPC_HOOK_CLI": "/tmp/foo"}):
            assert is_remote_dev_context() is True

    def test_remote_containers_true(self) -> None:
        with mock.patch.dict(os.environ, {"REMOTE_CONTAINERS": "true"}):
            assert is_remote_dev_context() is True

    def test_codespaces_true(self) -> None:
        with mock.patch.dict(os.environ, {"CODESPACES": "true"}):
            assert is_remote_dev_context() is True
