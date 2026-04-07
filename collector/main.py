"""CLI entrypoint: runs scans, scores confidence, evaluates policy, emits events.

One-shot mode (default):
    python -m collector.main --dry-run

Daemon mode (persistent endpoint agent):
    python -m collector.main \\
        --api-url http://localhost:8000/api \\
        --api-key <key> \\
        --interval 300 \\
        --report-all          # omit to report changes only
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

# Path bootstrap: collector/__init__.py (runs when package is loaded via python -m collector.main or detec-agent)
from config_loader import (
    SENTINEL_DEFAULTS,
    argparse_defaults,
    load_collector_config,
    save_server_interval,
)
from enforcement.cleanup import cleanup_orphaned_rules
from enforcement.posture import PostureManager
from enforcement.enforcer import Enforcer
from agent.state import DisabledServiceTracker, StateDiffer

try:
    from collector.output.adaptive_emitter import AdaptiveEmitter
    from collector.output.emitter import EventEmitter
    from collector.output.http_emitter import HttpEmitter
    from collector.output.tcp_emitter import TcpEmitter
except ImportError:
    from output.adaptive_emitter import AdaptiveEmitter
    from output.emitter import EventEmitter
    from output.http_emitter import HttpEmitter
    from output.tcp_emitter import TcpEmitter
from providers import get_best_provider

from orchestrator import EVENT_VERSION, build_event, run_scan
from collector.ipc.pipe_server import PipeServer

logger = logging.getLogger(__name__)


def _heartbeat_loop(
    emitter: HttpEmitter | TcpEmitter | AdaptiveEmitter,
    hostname: str,
    interval_holder: dict[str, int],
    stop_event: threading.Event,
    telemetry_provider: str = "polling",
    disabled_svc_tracker: DisabledServiceTracker | None = None,
) -> None:
    """Background thread: send heartbeats every interval seconds."""
    while not stop_event.wait(timeout=interval_holder["interval"]):
        kwargs: dict[str, Any] = {
            "hostname": hostname,
            "interval_seconds": interval_holder["interval"],
            "telemetry_provider": telemetry_provider,
        }
        use_http_hb = isinstance(emitter, HttpEmitter) or (
            isinstance(emitter, AdaptiveEmitter) and emitter.uses_http_heartbeat()
        )
        if disabled_svc_tracker and use_http_hb:
            kwargs["disabled_services"] = disabled_svc_tracker.to_heartbeat_payload()
        emitter.heartbeat(**kwargs)


def _build_lifecycle_event(
    event_type: str,
    endpoint_id: str,
    actor_id: str,
    summary: str,
) -> dict[str, Any]:
    """Build a lightweight lifecycle event (heartbeat/shutdown)."""
    import platform
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    session_id = str(uuid.uuid4())
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_version": EVENT_VERSION,
        "observed_at": now,
        "ingested_at": now,
        "session_id": session_id,
        "trace_id": f"trace-lifecycle-{session_id[:8]}",
        "parent_event_id": None,
        "actor": {
            "id": actor_id,
            "type": "automation",
            "trust_tier": "T1",
            "identity_confidence": 1.0,
            "org_context": "unknown",
        },
        "endpoint": {
            "id": endpoint_id,
            "os": f"{platform.system()} {platform.release()} {platform.machine()}",
            "posture": "unmanaged",
        },
        "action": {
            "type": "exec",
            "risk_class": "R1",
            "summary": summary,
            "raw_ref": f"evidence://collector-lifecycle/{endpoint_id}/{session_id}",
        },
        "target": {
            "type": "host",
            "id": endpoint_id,
            "scope": "local endpoint",
            "sensitivity_tier": "Tier0",
        },
        "tool": {
            "name": "agentic-gov-collector",
            "class": "A",
            "version": EVENT_VERSION,
            "attribution_confidence": 1.0,
            "attribution_sources": ["process"],
        },
        "severity": {"level": "S0"},
    }


_PID_DIR = Path.home() / ".agentic-gov"
_PID_FILE = _PID_DIR / "agent.pid"


def _write_pid_file() -> None:
    _PID_DIR.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()))


def _remove_pid_file() -> None:
    try:
        _PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _pid_cmdline_looks_like_detec(pid: int) -> bool:
    """True if process appears to be this agent (not a random reused PID)."""
    if sys.platform not in ("darwin", "linux"):
        return True
    try:
        r = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            return False
        s = (r.stdout or "").strip().lower()
        return "collector.main" in s or "detec-agent" in s or "detec_agent" in s
    except (OSError, subprocess.SubprocessError, ValueError):
        return False


def _acquire_pid_file() -> None:
    if _PID_FILE.exists():
        try:
            old_pid = int(_PID_FILE.read_text().strip())
        except ValueError:
            _remove_pid_file()
        else:
            try:
                os.kill(old_pid, 0)
            except (ProcessLookupError, OSError, SystemError):
                _remove_pid_file()
            else:
                if _pid_cmdline_looks_like_detec(old_pid):
                    print(
                        f"Another agent instance appears to be running (PID {old_pid}). "
                        f"Remove {_PID_FILE} if this is stale.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                _remove_pid_file()
    _write_pid_file()


def _run_daemon(args: argparse.Namespace) -> None:
    """Run the collector as a persistent daemon until SIGINT/SIGTERM."""
    _acquire_pid_file()

    cleanup_orphaned_rules()

    hostname = args.endpoint_id
    protocol = getattr(args, "protocol", "auto")

    posture_mgr = PostureManager(
        initial_posture=getattr(args, "enforcement_posture", "passive"),
        initial_threshold=getattr(args, "auto_enforce_threshold", 0.75),
    )
    if getattr(args, "enforce", False):
        import warnings

        warnings.warn(
            "--enforce is deprecated and will be removed in a future release. "
            "Use --posture active instead, or set posture from the central server.",
            DeprecationWarning,
            stacklevel=2,
        )
        posture_mgr.update("active", source="cli_override")
    elif "--posture" in sys.argv:
        posture_mgr.update(
            getattr(args, "enforcement_posture", "passive"),
            source="cli_override",
        )
    disabled_svc_tracker = DisabledServiceTracker()
    enforcer = Enforcer(
        posture_manager=posture_mgr,
        dry_run=args.dry_run,
        disabled_service_tracker=disabled_svc_tracker,
        allow_linux_uid_fallback=getattr(args, "allow_linux_uid_block_fallback", False),
    )

    def _on_restore(service_ids: list[str]) -> None:
        from enforcement.service_restore import restore_by_ids

        results = restore_by_ids(service_ids, disabled_svc_tracker)
        for sid, ok in results.items():
            logger.info("Service restore %s: %s", sid, "success" if ok else "failed")

    def _on_posture(
        posture: str,
        auto_enforce_threshold: float | None = None,
        allow_list: list[str] | None = None,
        llm_hosts: list[str] | None = None,
    ) -> None:
        posture_mgr.update(
            posture,
            auto_enforce_threshold=auto_enforce_threshold,
            allow_list=allow_list,
            source="server_push",
        )
        if llm_hosts:
            from scanner.behavioral_patterns import update_llm_hosts

            update_llm_hosts(set(llm_hosts))

    current_interval_holder: dict[str, int] = {"interval": args.interval}

    def _on_interval(interval_seconds: int) -> None:
        current_interval_holder["interval"] = interval_seconds
        save_server_interval(interval_seconds)
        logger.info("Applied server interval_seconds=%s", interval_seconds)

    def _on_command(command: str, command_id: str, params: dict) -> None:
        if command == "restore_services":
            svc_ids = params.get("service_ids", [])
            logger.info(
                "Received restore_services command (id=%s, services=%s)",
                command_id,
                svc_ids,
            )
            if svc_ids:
                _on_restore(svc_ids)
            else:
                from enforcement.service_restore import restore_all

                restore_all(disabled_svc_tracker)
        elif command == "kill_process":
            pid = params.get("pid")
            process_name = params.get("process_name", "")
            tool_name = params.get("tool_name", "")
            logger.info(
                "Received kill_process command (id=%s, pid=%s, process=%s, tool=%s)",
                command_id,
                pid,
                process_name,
                tool_name,
            )
            if pid is not None:
                try:
                    import psutil
                    from enforcement.process_kill import kill_process_tree

                    result = kill_process_tree(
                        pid=int(pid),
                        expected_pattern=process_name or tool_name or None,
                    )
                    if result.success:
                        logger.info(
                            "kill_process command succeeded: %s (pid=%s, killed=%s)",
                            result.detail,
                            pid,
                            result.killed_pids,
                        )
                    else:
                        logger.warning(
                            "kill_process command failed: %s (pid=%s)",
                            result.detail,
                            pid,
                        )
                except Exception:
                    logger.exception(
                        "kill_process command raised an exception (pid=%s)", pid
                    )
            else:
                logger.warning("kill_process command missing pid (id=%s)", command_id)
        else:
            logger.info("Unhandled command: %s (id=%s)", command, command_id)

    gateway_host = getattr(args, "gateway_host", None)
    gateway_port = int(getattr(args, "gateway_port", 8001) or 8001)
    if not gateway_host:
        from urllib.parse import urlparse

        parsed = urlparse(args.api_url)
        gateway_host = parsed.hostname or "localhost"

    auto_tls = args.api_url.startswith("https://") if args.api_url else False
    tls_enabled = getattr(args, "tls", auto_tls)
    if not tls_enabled and auto_tls:
        tls_enabled = True

    if protocol == "auto":
        if not args.api_url or not args.api_key:
            print(
                "protocol auto requires --api-url and --api-key.",
                file=sys.stderr,
            )
            sys.exit(1)
        emitter = AdaptiveEmitter(
            api_url=args.api_url,
            api_key=args.api_key,
            hostname=hostname,
            agent_version=EVENT_VERSION,
            gateway_host=gateway_host,
            gateway_port=gateway_port,
            tls=tls_enabled,
            tcp_connect_timeout=float(
                getattr(args, "tcp_connect_timeout_seconds", 3.0) or 3.0
            ),
            tcp_retry_interval=float(
                getattr(args, "tcp_retry_interval_seconds", 30.0) or 30.0
            ),
            tcp_failure_threshold=int(getattr(args, "tcp_failure_threshold", 5) or 5),
            tcp_recovery_stability=float(
                getattr(args, "tcp_recovery_stability_seconds", 10.0) or 10.0
            ),
            on_posture=_on_posture,
            on_restore=_on_restore,
            on_interval=_on_interval,
            on_command=_on_command,
        )
    elif protocol == "tcp":
        if (
            not tls_enabled
            and args.api_url
            and not args.api_url.startswith("http://localhost")
        ):
            logger.warning(
                "TCP transport running without TLS. Set --tls or use https:// API URL "
                "to enable encrypted transport."
            )
        emitter = TcpEmitter(
            gateway_host=gateway_host,
            gateway_port=gateway_port,
            api_key=args.api_key,
            hostname=hostname,
            agent_version=EVENT_VERSION,
            tls=tls_enabled,
            on_posture=_on_posture,
            on_command=_on_command,
        )
    else:
        emitter = HttpEmitter(
            api_url=args.api_url,
            api_key=args.api_key,
            on_posture=_on_posture,
            on_restore=_on_restore,
            on_interval=_on_interval,
        )

    differ = StateDiffer(report_all=args.report_all)

    stop_event = threading.Event()
    scan_trigger = threading.Event()

    def _on_alert(event: object) -> None:
        logger.info(
            "Alert-triggered scan requested (pid=%s)", getattr(event, "pid", "?")
        )
        scan_trigger.set()

    args._on_alert = _on_alert  # type: ignore[attr-defined]

    def _handle_signal(signum: int, frame: Any) -> None:
        print(f"\nReceived signal {signum}, shutting down daemon...", file=sys.stderr)
        stop_event.set()
        scan_trigger.set()

    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except (ValueError, OSError):
        pass

    telemetry_preference = getattr(args, "telemetry_provider", "auto")
    resolved_provider = get_best_provider(telemetry_preference)
    telemetry_provider_name = resolved_provider.name

    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(
            emitter,
            hostname,
            current_interval_holder,
            stop_event,
            telemetry_provider_name,
            disabled_svc_tracker,
        ),
        daemon=True,
        name="heartbeat",
    )
    heartbeat_thread.start()

    print(
        f"Agentic-gov endpoint agent started — "
        f"interval={current_interval_holder['interval']}s  api={args.api_url}  "
        f"mode={'report-all' if args.report_all else 'changes-only'}",
        file=sys.stderr,
    )

    last_scan_time: str | None = None
    events_sent: int = 0
    _watchdog_check_cycle: int = 0

    pipe_server = PipeServer(
        status_provider=lambda: {
            "connected": emitter.connected if hasattr(emitter, "connected") else True,
            "last_scan": last_scan_time,
            "events_sent": events_sent,
            "version": EVENT_VERSION,
        },
        scan_callback=lambda: run_scan(args, emitter, pipe_server=pipe_server),
    )
    pipe_server.start()

    while not stop_event.is_set():
        flushed = emitter.flush_buffer()
        if flushed and args.verbose:
            print(f"Flushed {flushed} buffered events")

        triggered = scan_trigger.is_set()
        scan_trigger.clear()
        scan_source = "alert-triggered" if triggered else "scheduled"
        logger.info("Starting %s scan cycle", scan_source)

        run_scan(
            args,
            emitter=emitter,
            state_differ=differ,
            posture_manager=posture_mgr,
            enforcer=enforcer,
            pipe_server=pipe_server,
        )

        from datetime import datetime, timezone

        last_scan_time = datetime.now(timezone.utc).isoformat()
        events_sent = (
            emitter.stats.get("emitted", 0)
            if hasattr(emitter, "stats")
            else events_sent
        )

        # Mutual monitoring: ensure the watchdog task is still registered.
        # Only check every 5 scan cycles to avoid unnecessary overhead.
        if sys.platform == "win32":
            _watchdog_check_cycle += 1
            if _watchdog_check_cycle >= 5:
                _watchdog_check_cycle = 0
                try:
                    from watchdog import (
                        _WATCHDOG_TASK_NAME,
                        _AGENT_EXE_PATH,
                        is_task_registered,
                    )

                    if not is_task_registered(_WATCHDOG_TASK_NAME):
                        logger.warning(
                            "Watchdog task '%s' not found — re-registering",
                            _WATCHDOG_TASK_NAME,
                        )
                        _watchdog_exe = _AGENT_EXE_PATH
                        import subprocess as _sp

                        _sp.run(
                            [
                                "schtasks",
                                "/create",
                                "/tn",
                                _WATCHDOG_TASK_NAME,
                                "/tr",
                                f"'{_watchdog_exe}' watchdog",
                                "/sc",
                                "onstart",
                                "/ru",
                                "SYSTEM",
                                "/rl",
                                "HIGHEST",
                                "/f",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        _sp.run(
                            ["schtasks", "/run", "/tn", _WATCHDOG_TASK_NAME],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                except Exception:
                    logger.exception("Failed to check/restore watchdog task")

        scan_trigger.wait(timeout=current_interval_holder["interval"])
        if stop_event.is_set():
            break

    pipe_server.stop()

    shutdown_event = _build_lifecycle_event(
        event_type="agent.shutdown",
        endpoint_id=hostname,
        actor_id=args.actor_id,
        summary="Collector agent shutting down gracefully",
    )
    emitter.emit(shutdown_event)

    if isinstance(emitter, TcpEmitter):
        emitter.shutdown()
    elif isinstance(emitter, AdaptiveEmitter):
        emitter.shutdown()

    stop_event.set()
    cleanup_orphaned_rules()
    _remove_pid_file()
    print("Agentic-gov endpoint agent stopped.", file=sys.stderr)


def _run_local_daemon(args: argparse.Namespace) -> None:
    """Run the collector in local-only mode — no API server needed.

    Scans on interval, writes events to NDJSON file, enforces local policy,
    and prints a summary to stderr after each cycle.
    """
    _acquire_pid_file()
    cleanup_orphaned_rules()

    hostname = args.endpoint_id

    posture_mgr = PostureManager(
        initial_posture=getattr(args, "enforcement_posture", "passive"),
        initial_threshold=getattr(args, "auto_enforce_threshold", 0.75),
    )
    if getattr(args, "enforce", False):
        posture_mgr.update("active", source="cli_override")
    elif "--posture" in sys.argv:
        posture_mgr.update(
            getattr(args, "enforcement_posture", "passive"),
            source="cli_override",
        )

    disabled_svc_tracker = DisabledServiceTracker()
    enforcer = Enforcer(
        posture_manager=posture_mgr,
        dry_run=args.dry_run,
        disabled_service_tracker=disabled_svc_tracker,
    )

    output_path = getattr(args, "output", None) or "./scan-results.ndjson"
    emitter = EventEmitter(output_path)
    differ = StateDiffer(report_all=args.report_all)

    stop_event = threading.Event()

    def _handle_signal(signum: int, frame: Any) -> None:
        print(f"\nReceived signal {signum}, shutting down...", file=sys.stderr)
        stop_event.set()

    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except (ValueError, OSError):
        pass

    print(
        f"Detec agent started (local mode) — "
        f"interval={args.interval}s  output={output_path}  "
        f"posture={posture_mgr.posture}",
        file=sys.stderr,
    )

    while not stop_event.is_set():
        run_scan(
            args,
            emitter=emitter,
            state_differ=differ,
            posture_manager=posture_mgr,
            enforcer=enforcer,
        )
        stop_event.wait(timeout=args.interval)

    cleanup_orphaned_rules()
    _remove_pid_file()
    print("Detec agent stopped.", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Endpoint telemetry collector for agentic AI tool detection",
    )
    parser.add_argument(
        "--output",
        help="Output file for NDJSON events (default: ./scan-results.ndjson)",
    )
    parser.add_argument(
        "--endpoint-id",
        help="Endpoint identifier (default: hostname)",
    )
    parser.add_argument(
        "--actor-id",
        help="Actor/user identifier (default: current OS user)",
    )
    parser.add_argument(
        "--sensitivity",
        choices=["Tier0", "Tier1", "Tier2", "Tier3"],
        help="Asset sensitivity tier (default: Tier0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Print events to stdout instead of writing to file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=None,
        help="Print detailed scan progress",
    )
    parser.add_argument(
        "--interval",
        type=int,
        metavar="SECONDS",
        help="Run as persistent daemon, scanning every N seconds (0 = one-shot)",
    )
    parser.add_argument(
        "--api-url",
        metavar="URL",
        help="Central API base URL, e.g. http://localhost:8000/api",
    )
    parser.add_argument(
        "--api-key",
        metavar="KEY",
        help="API key for authenticating with the central server",
    )
    parser.add_argument(
        "--report-all",
        action="store_true",
        default=None,
        help="Report all detections every cycle (default: changes only)",
    )
    parser.add_argument(
        "--posture",
        dest="enforcement_posture",
        choices=["passive", "audit", "active"],
        help="Enforcement posture (default: passive, or as set by central server)",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        default=False,
        help="[DEPRECATED] Use --posture active instead",
    )
    parser.add_argument(
        "--auto-enforce-threshold",
        dest="auto_enforce_threshold",
        type=float,
        metavar="SCORE",
        help="Minimum confidence for auto-enforcement in active posture (default: 0.75)",
    )
    parser.add_argument(
        "--protocol",
        choices=["auto", "http", "tcp"],
        default="auto",
        help="Transport: auto (TCP first, HTTP fallback), tcp, or http (default: auto)",
    )
    parser.add_argument(
        "--gateway-host",
        dest="gateway_host",
        metavar="HOST",
        help="Gateway host for TCP protocol (default: derived from --api-url)",
    )
    parser.add_argument(
        "--gateway-port",
        dest="gateway_port",
        type=int,
        default=8001,
        help="Gateway port for TCP protocol (default: 8001)",
    )
    parser.add_argument(
        "--tcp-connect-timeout",
        dest="tcp_connect_timeout_seconds",
        type=float,
        metavar="SEC",
        default=None,
        help="TCP auth probe timeout for protocol auto (default: 3)",
    )
    parser.add_argument(
        "--tcp-retry-interval",
        dest="tcp_retry_interval_seconds",
        type=float,
        metavar="SEC",
        default=None,
        help="Interval between TCP recovery probes when on HTTP (default: 30)",
    )
    parser.add_argument(
        "--tcp-failure-threshold",
        dest="tcp_failure_threshold",
        type=int,
        metavar="N",
        default=None,
        help="Consecutive TCP reconnect failures before HTTP fallback (default: 5)",
    )
    parser.add_argument(
        "--tcp-recovery-stability",
        dest="tcp_recovery_stability_seconds",
        type=float,
        metavar="SEC",
        default=None,
        help="Seconds TCP must stay reachable before switching back (default: 10)",
    )
    parser.add_argument(
        "--telemetry-provider",
        choices=["auto", "native", "polling"],
        default="auto",
        help="Telemetry provider preference (default: auto)",
    )
    parser.add_argument(
        "--sentinel",
        action="store_true",
        dest="sentinel_enabled",
        help="Enable adaptive sentinel (probe) mode",
    )

    parser.set_defaults(**argparse_defaults())

    args = parser.parse_args()

    full_cfg = load_collector_config()
    _ad_defaults = argparse_defaults()
    for _k in (
        "tcp_connect_timeout_seconds",
        "tcp_retry_interval_seconds",
        "tcp_failure_threshold",
        "tcp_recovery_stability_seconds",
    ):
        if getattr(args, _k, None) is None:
            setattr(args, _k, _ad_defaults.get(_k))
    args.sentinel = full_cfg.get("sentinel", SENTINEL_DEFAULTS)
    if getattr(args, "sentinel_enabled", False):
        args.sentinel = {**args.sentinel, "enabled": True}

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.interval > 0:
        if not args.api_url or not args.api_key:
            parser.error("--interval requires both --api-url and --api-key")
        _run_daemon(args)
    else:
        sys.exit(run_scan(args))


if __name__ == "__main__":
    main()
