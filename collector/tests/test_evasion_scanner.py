"""Tests for the evasion detection scanner."""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scanner.evasion import (
    EvasionScanner,
    HOOK_STRIP_PATTERNS,
    KNOWN_AI_BINARIES,
    EvasionFinding,
)
from scanner.base import ScanResult


@pytest.fixture
def scanner():
    return EvasionScanner()


@pytest.fixture
def tmp_git_repo(tmp_path):
    """Create a temporary git-like directory structure."""
    git_dir = tmp_path / "repo" / ".git"
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True)
    logs_dir = git_dir / "logs"
    logs_dir.mkdir(parents=True)
    return git_dir


class TestStripPatternMatching:
    """Test the regex patterns that detect Co-Authored-By stripping."""

    def test_grep_v_co_authored(self):
        content = 'grep -v "Co-Authored-By" "$1" > tmp && mv tmp "$1"'
        assert any(p.search(content) for p in HOOK_STRIP_PATTERNS)

    def test_sed_co_authored(self):
        content = "sed -i '/Co-Authored-By/d' $1"
        assert any(p.search(content) for p in HOOK_STRIP_PATTERNS)

    def test_awk_co_authored(self):
        content = "awk '!/Co-Authored-By/' $1 > tmp && mv tmp $1"
        assert any(p.search(content) for p in HOOK_STRIP_PATTERNS)

    def test_case_insensitive_match(self):
        content = 'grep -v "co-authored-by" "$1"'
        assert any(p.search(content) for p in HOOK_STRIP_PATTERNS)

    def test_no_match_on_normal_hook(self):
        content = textwrap.dedent("""\
            #!/bin/sh
            # Simple commit-msg hook
            if ! grep -q "^Fixes:" "$1"; then
                echo "Missing Fixes: reference"
                exit 1
            fi
        """)
        assert not any(p.search(content) for p in HOOK_STRIP_PATTERNS)


class TestGlobalHookDetection:
    def test_global_hook_with_stripping(self, scanner, tmp_path):
        hooks_dir = tmp_path / "global-hooks"
        hooks_dir.mkdir()
        commit_msg = hooks_dir / "commit-msg"
        commit_msg.write_text('#!/bin/sh\ngrep -v "Co-Authored-By" "$1" > tmp && mv tmp "$1"')

        with patch.object(scanner, "_get_git_config", return_value=str(hooks_dir)):
            findings = scanner._check_global_hooks(verbose=False)

        assert len(findings) == 1
        assert findings[0].vector == "E1-global-hook"
        assert findings[0].boost == 0.15

    def test_global_hook_no_stripping(self, scanner, tmp_path):
        hooks_dir = tmp_path / "global-hooks"
        hooks_dir.mkdir()
        commit_msg = hooks_dir / "commit-msg"
        commit_msg.write_text("#!/bin/sh\necho 'checking commit'\nexit 0")

        with patch.object(scanner, "_get_git_config", return_value=str(hooks_dir)):
            findings = scanner._check_global_hooks(verbose=False)

        assert len(findings) == 0

    def test_no_global_hooks_path(self, scanner):
        with patch.object(scanner, "_get_git_config", return_value=None):
            findings = scanner._check_global_hooks(verbose=False)
        assert len(findings) == 0


class TestTemplateHookDetection:
    def test_template_hook_with_stripping(self, scanner, tmp_path):
        tmpl_dir = tmp_path / "templates"
        hooks_dir = tmpl_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        commit_msg = hooks_dir / "commit-msg"
        commit_msg.write_text('#!/bin/sh\nsed -i "/Co-Authored-By/d" "$1"')

        with patch.object(scanner, "_get_git_config", return_value=str(tmpl_dir)):
            findings = scanner._check_template_hooks(verbose=False)

        assert len(findings) == 1
        assert findings[0].vector == "E2-template-hook"
        assert findings[0].boost == 0.20

    def test_no_template_dir(self, scanner):
        with patch.object(scanner, "_get_git_config", return_value=None):
            findings = scanner._check_template_hooks(verbose=False)
        assert len(findings) == 0


class TestRepoHookDetection:
    def test_repo_hook_with_stripping(self, scanner, tmp_git_repo):
        hook = tmp_git_repo / "hooks" / "commit-msg"
        hook.write_text('#!/bin/sh\ngrep -v "co-authored-by" "$1" > tmp && mv tmp "$1"')

        with patch.object(scanner, "_find_git_repos", return_value=[tmp_git_repo]):
            findings = scanner._check_repo_hooks(verbose=False)

        assert len(findings) == 1
        assert findings[0].vector == "E1-repo-hook"
        assert findings[0].boost == 0.15

    def test_repo_without_hook(self, scanner, tmp_git_repo):
        with patch.object(scanner, "_find_git_repos", return_value=[tmp_git_repo]):
            findings = scanner._check_repo_hooks(verbose=False)
        assert len(findings) == 0


class TestForcePushDetection:
    def test_amend_then_push_in_reflog(self, scanner, tmp_git_repo):
        reflog = tmp_git_repo / "logs" / "HEAD"
        reflog.write_text(textwrap.dedent("""\
            abc123 def456 User <u@e.com> 1710000000 +0000\tcommit: initial
            def456 ghi789 User <u@e.com> 1710001000 +0000\tcommit (amend): fix typo
            ghi789 jkl012 User <u@e.com> 1710002000 +0000\tpush: updating refs
        """))

        with patch.object(scanner, "_find_git_repos", return_value=[tmp_git_repo]):
            findings = scanner._check_force_push_patterns(verbose=False)

        assert len(findings) == 1
        assert findings[0].vector == "E3-force-push"
        assert findings[0].boost == 0.10

    def test_normal_push_no_amend(self, scanner, tmp_git_repo):
        reflog = tmp_git_repo / "logs" / "HEAD"
        reflog.write_text(textwrap.dedent("""\
            abc123 def456 User <u@e.com> 1710000000 +0000\tcommit: initial
            def456 ghi789 User <u@e.com> 1710001000 +0000\tcommit: add feature
            ghi789 jkl012 User <u@e.com> 1710002000 +0000\tpush: updating refs
        """))

        with patch.object(scanner, "_find_git_repos", return_value=[tmp_git_repo]):
            findings = scanner._check_force_push_patterns(verbose=False)

        assert len(findings) == 0

    def test_no_reflog(self, scanner, tmp_git_repo):
        with patch.object(scanner, "_find_git_repos", return_value=[tmp_git_repo]):
            findings = scanner._check_force_push_patterns(verbose=False)
        assert len(findings) == 0


class TestRenamedBinaryDetection:
    def test_renamed_binary_detected(self, scanner):
        # Process 123 (myapp) is child of 456 (cursor); cmd mentions claude -> E4.
        ps_table = "456 1 cursor\n123 456 myapp\n"
        ps_aux = textwrap.dedent("""\
            USER  PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND
            user  123  1.0  0.5 100 50 ? S 10:00 0:01 /usr/local/bin/myapp --flag claude-code-agent
        """)
        mock_table = MagicMock()
        mock_table.returncode = 0
        mock_table.stdout = ps_table
        mock_aux = MagicMock()
        mock_aux.returncode = 0
        mock_aux.stdout = ps_aux

        with patch.object(scanner, "_run_cmd", side_effect=[mock_table, mock_aux]):
            findings = scanner._check_renamed_binaries(verbose=False)

        assert len(findings) == 1
        assert findings[0].vector == "E4-renamed-binary"
        assert findings[0].boost == 0.08

    def test_normal_binary_not_flagged(self, scanner):
        ps_table = "123 1 cursor\n"
        ps_aux = textwrap.dedent("""\
            USER  PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND
            user  123  1.0  0.5 100 50 ? S 10:00 0:01 /usr/local/bin/cursor --flag
        """)
        mock_table = MagicMock()
        mock_table.returncode = 0
        mock_table.stdout = ps_table
        mock_aux = MagicMock()
        mock_aux.returncode = 0
        mock_aux.stdout = ps_aux

        with patch.object(scanner, "_run_cmd", side_effect=[mock_table, mock_aux]):
            findings = scanner._check_renamed_binaries(verbose=False)

        assert len(findings) == 0

    def test_evasion_e4_false_positive_cursor_process_tree(self, scanner):
        # Cursor -> Electron -> node with "cursor" in args: normal subprocesses, no E4.
        ps_table = textwrap.dedent("""\
            100 1 cursor
            101 100 electron
            102 101 node
        """)
        ps_aux = textwrap.dedent("""\
            USER  PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND
            user  100  0.5  1.0 100 50 ? S 10:00 0:00 /Applications/Cursor.app/Contents/MacOS/Cursor
            user  101  0.3  0.8 100 50 ? S 10:01 0:00 /Applications/Cursor.app/Contents/Frameworks/Electron
            user  102  0.2  0.5 100 50 ? S 10:02 0:00 node /path/to/cursor/helper.js
        """)
        mock_table = MagicMock()
        mock_table.returncode = 0
        mock_table.stdout = ps_table
        mock_aux = MagicMock()
        mock_aux.returncode = 0
        mock_aux.stdout = ps_aux

        with patch.object(scanner, "_run_cmd", side_effect=[mock_table, mock_aux]):
            findings = scanner._check_renamed_binaries(verbose=False)

        assert len(findings) == 0

    def test_ps_command_fails(self, scanner):
        with patch.object(scanner, "_run_cmd", return_value=None):
            findings = scanner._check_renamed_binaries(verbose=False)
        assert len(findings) == 0


class TestCursorSettingsDetection:
    def test_cursor_git_disabled(self, scanner, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({"git.enabled": False}))

        with patch(
            "scanner.evasion.CURSOR_SETTINGS_PATHS",
            [settings],
        ):
            findings = scanner._check_cursor_settings(verbose=False)

        assert len(findings) == 1
        assert findings[0].vector == "E5-cursor-git-disabled"
        assert findings[0].boost == 0.10

    def test_cursor_telemetry_off(self, scanner, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({"telemetry.telemetryLevel": "off"}))

        with patch(
            "scanner.evasion.CURSOR_SETTINGS_PATHS",
            [settings],
        ):
            findings = scanner._check_cursor_settings(verbose=False)

        assert len(findings) == 1
        assert findings[0].vector == "E5-cursor-telemetry-off"
        assert findings[0].boost == 0.05

    def test_normal_cursor_settings(self, scanner, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({"editor.fontSize": 14}))

        with patch(
            "scanner.evasion.CURSOR_SETTINGS_PATHS",
            [settings],
        ):
            findings = scanner._check_cursor_settings(verbose=False)

        assert len(findings) == 0

    def test_missing_settings_file(self, scanner, tmp_path):
        with patch(
            "scanner.evasion.CURSOR_SETTINGS_PATHS",
            [tmp_path / "nonexistent.json"],
        ):
            findings = scanner._check_cursor_settings(verbose=False)
        assert len(findings) == 0


class TestFullScan:
    def test_clean_system_no_evasion(self, scanner):
        with (
            patch.object(scanner, "_check_global_hooks", return_value=[]),
            patch.object(scanner, "_check_template_hooks", return_value=[]),
            patch.object(scanner, "_check_repo_hooks", return_value=[]),
            patch.object(scanner, "_check_force_push_patterns", return_value=[]),
            patch.object(scanner, "_check_renamed_binaries", return_value=[]),
            patch.object(scanner, "_check_cursor_settings", return_value=[]),
        ):
            result = scanner.scan(verbose=False)

        assert not result.detected
        assert result.evasion_boost == 0.0

    def test_multiple_evasion_indicators(self, scanner):
        findings = [
            EvasionFinding("E1-global-hook", "Global hook", "/hooks/commit-msg", 0.15),
            EvasionFinding("E2-template-hook", "Template hook", "/templates/hooks/commit-msg", 0.20),
            EvasionFinding("E3-force-push", "Force push after amend", "/repo", 0.10),
        ]

        with (
            patch.object(scanner, "_check_global_hooks", return_value=findings[:1]),
            patch.object(scanner, "_check_template_hooks", return_value=findings[1:2]),
            patch.object(scanner, "_check_repo_hooks", return_value=[]),
            patch.object(scanner, "_check_force_push_patterns", return_value=findings[2:]),
            patch.object(scanner, "_check_renamed_binaries", return_value=[]),
            patch.object(scanner, "_check_cursor_settings", return_value=[]),
        ):
            result = scanner.scan(verbose=False)

        assert result.detected
        assert abs(result.evasion_boost - 0.45) < 1e-9
        assert len(result.evidence_details["evasion_findings"]) == 3
        assert result.signals.behavior == 0.8

    def test_evasion_boost_capped_at_050(self, scanner):
        many_findings = [
            EvasionFinding(f"E{i}", f"Finding {i}", None, 0.20)
            for i in range(5)
        ]
        with (
            patch.object(scanner, "_check_global_hooks", return_value=many_findings[:2]),
            patch.object(scanner, "_check_template_hooks", return_value=many_findings[2:4]),
            patch.object(scanner, "_check_repo_hooks", return_value=many_findings[4:]),
            patch.object(scanner, "_check_force_push_patterns", return_value=[]),
            patch.object(scanner, "_check_renamed_binaries", return_value=[]),
            patch.object(scanner, "_check_cursor_settings", return_value=[]),
        ):
            result = scanner.scan(verbose=False)

        assert result.evasion_boost == 0.50


class TestHelpers:
    def test_safe_read_normal_file(self, scanner, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert scanner._safe_read(f) == "hello"

    def test_safe_read_missing_file(self, scanner, tmp_path):
        assert scanner._safe_read(tmp_path / "missing.txt") is None

    def test_safe_read_oversized_file(self, scanner, tmp_path):
        f = tmp_path / "big.txt"
        f.write_text("x" * (65 * 1024))
        assert scanner._safe_read(f) is None

    def test_has_strip_pattern_positive(self):
        assert EvasionScanner._has_strip_pattern('grep -v "Co-Authored-By"')

    def test_has_strip_pattern_negative(self):
        assert not EvasionScanner._has_strip_pattern("echo hello")
