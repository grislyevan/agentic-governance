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
from output.http_emitter import HttpEmitter
from output.tcp_emitter import TcpEmitter
from providers import get_best_provider

from orchestrator import EVENT_VERSION, build_event, run_scan

logger = logging.getLogger(__name__)


def _heartbeat_loop(
    emitter: HttpEmitter | TcpEmitter,
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
        if disabled_svc_tracker and isinstance(emitter, HttpEmitter):
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


def _run_daemon(args: argparse.Namespace) -> None:
    """Run the collector as a persistent daemon until SIGINT/SIGTERM."""
    if _PID_FILE.exists():
        try:
            old_pid = int(_PID_FILE.read_text().strip())
            os.kill(old_pid, 0)
            print(
                f"Another agent instance appears to be running (PID {old_pid}). "
                f"Remove {_PID_FILE} if this is stale.",
                file=sys.stderr,
            )
            sys.exit(1)
        except (ProcessLookupError, ValueError, OSError):
            pass

    _write_pid_file()

    cleanup_orphaned_rules()

    hostname = args.endpoint_id
    protocol = getattr(args, "protocol", "http")

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

    if protocol == "tcp":
        gateway_host = getattr(args, "gateway_host", None)
        gateway_port = getattr(args, "gateway_port", 8001)

        if not gateway_host:
            from urllib.parse import urlparse
            parsed = urlparse(args.api_url)
            gateway_host = parsed.hostname or "localhost"

        auto_tls = args.api_url.startswith("https://") if args.api_url else False
        tls_enabled = getattr(args, "tls", auto_tls)
        if not tls_enabled and auto_tls:
            tls_enabled = True
        if not tls_enabled and args.api_url and not args.api_url.startswith("http://localhost"):
            logger.warning(
                "TCP transport running without TLS. Set --tls or use https:// API URL "
                "to enable encrypted transport."
            )

        def _on_command(command: str, command_id: str, params: dict) -> None:
            if command == "restore_services":
                svc_ids = params.get("service_ids", [])
                logger.info("Received restore_services command (id=%s, services=%s)", command_id, svc_ids)
                if svc_ids:
                    _on_restore(svc_ids)
                else:
                    from enforcement.service_restore import restore_all
                    restore_all(disabled_svc_tracker)
            else:
                logger.info("Unhandled command: %s (id=%s)", command, command_id)

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
        logger.info("Alert-triggered scan requested (pid=%s)", getattr(event, "pid", "?"))
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
        args=(emitter, hostname, current_interval_holder, stop_event, telemetry_provider_name, disabled_svc_tracker),
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
        )

        scan_trigger.wait(timeout=current_interval_holder["interval"])
        if stop_event.is_set():
            break

    shutdown_event = _build_lifecycle_event(
        event_type="agent.shutdown",
        endpoint_id=hostname,
        actor_id=args.actor_id,
        summary="Collector agent shutting down gracefully",
    )
    emitter.emit(shutdown_event)

    if isinstance(emitter, TcpEmitter):
        emitter.shutdown()

    stop_event.set()
    cleanup_orphaned_rules()
    _remove_pid_file()
    print("Agentic-gov endpoint agent stopped.", file=sys.stderr)


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
        "--dry-run", action="store_true", default=None,
        help="Print events to stdout instead of writing to file",
    )
    parser.add_argument(
        "--verbose", action="store_true", default=None,
        help="Print detailed scan progress",
    )
    parser.add_argument(
        "--interval", type=int, metavar="SECONDS",
        help="Run as persistent daemon, scanning every N seconds (0 = one-shot)",
    )
    parser.add_argument(
        "--api-url", metavar="URL",
        help="Central API base URL, e.g. http://localhost:8000/api",
    )
    parser.add_argument(
        "--api-key", metavar="KEY",
        help="API key for authenticating with the central server",
    )
    parser.add_argument(
        "--report-all", action="store_true", default=None,
        help="Report all detections every cycle (default: changes only)",
    )
    parser.add_argument(
        "--posture", dest="enforcement_posture",
        choices=["passive", "audit", "active"],
        help="Enforcement posture (default: passive, or as set by central server)",
    )
    parser.add_argument(
        "--enforce", action="store_true", default=False,
        help="[DEPRECATED] Use --posture active instead",
    )
    parser.add_argument(
        "--auto-enforce-threshold", dest="auto_enforce_threshold",
        type=float, metavar="SCORE",
        help="Minimum confidence for auto-enforcement in active posture (default: 0.75)",
    )
    parser.add_argument(
        "--protocol", choices=["http", "tcp"], default="http",
        help="Transport protocol for daemon mode (default: http)",
    )
    parser.add_argument(
        "--gateway-host", dest="gateway_host", metavar="HOST",
        help="Gateway host for TCP protocol (default: derived from --api-url)",
    )
    parser.add_argument(
        "--gateway-port", dest="gateway_port", type=int, default=8001,
        help="Gateway port for TCP protocol (default: 8001)",
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
