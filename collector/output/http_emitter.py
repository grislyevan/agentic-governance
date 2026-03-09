"""HTTP transport layer for sending events to the central API.

Replaces the local NDJSON file write (EventEmitter) when running in
daemon/agent mode.  Uses only stdlib (urllib.request) — no extra deps
beyond ``cryptography`` for optional payload signing.

Retry policy: exponential backoff, up to 3 attempts per event.
On final failure, the event is appended to the local NDJSON buffer
(collector/agent/buffer.py) and will be flushed on the next successful
connection at the start of the following scan cycle.

Usage::

    emitter = HttpEmitter(api_url="http://localhost:8000/api", api_key="<key>")
    emitter.emit(event_dict)   # True = accepted, False = buffered locally
    emitter.flush_buffer()     # send any previously buffered events
"""

from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from collector.agent.buffer import LocalBuffer

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 10
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0  # seconds; doubles each attempt

try:
    from collector.crypto.signer import (
        load_signing_key,
        load_public_key_pem,
        get_key_fingerprint,
        sign_event,
    )
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


class HttpEmitter:
    """POST events to the central API with retry and local buffer fallback."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: int = _DEFAULT_TIMEOUT,
        buffer: LocalBuffer | None = None,
        sign_events: bool = True,
    ) -> None:
        self._api_url = api_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._buffer = buffer or LocalBuffer()
        self._ssl_ctx = ssl.create_default_context()
        self._sent = 0
        self._buffered = 0

        self._signing_key = None
        self._key_fingerprint: str | None = None
        if sign_events and _HAS_CRYPTO:
            self._signing_key = load_signing_key()
            if self._signing_key:
                pub_pem = load_public_key_pem()
                if pub_pem:
                    self._key_fingerprint = get_key_fingerprint(pub_pem)
                logger.info("Event signing enabled (fingerprint=%s)", self._key_fingerprint)

    # ------------------------------------------------------------------
    # Core emit
    # ------------------------------------------------------------------

    def emit(self, event: dict[str, Any]) -> bool:
        """Send a single event to POST /events.

        Returns True if accepted by the server, False if buffered locally.
        If a signing key is loaded, the event is signed before transmission.
        """
        if self._signing_key is not None and _HAS_CRYPTO:
            event["_signature"] = sign_event(event, self._signing_key)
            event["_key_fingerprint"] = self._key_fingerprint

        payload = json.dumps(event, separators=(",", ":")).encode("utf-8")
        url = f"{self._api_url}/events"

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=payload,
                    method="POST",
                    headers={
                        "Content-Type": "application/json",
                        "X-Api-Key": self._api_key,
                    },
                )
                with urllib.request.urlopen(req, timeout=self._timeout, context=self._ssl_ctx) as resp:
                    if resp.status in (200, 201, 202):
                        self._sent += 1
                        logger.debug(
                            "HttpEmitter: sent event %s (HTTP %d)",
                            event.get("event_id", "?"),
                            resp.status,
                        )
                        return True
                    logger.warning(
                        "HttpEmitter: unexpected HTTP %d for event %s (attempt %d/%d)",
                        resp.status,
                        event.get("event_id", "?"),
                        attempt,
                        _MAX_RETRIES,
                    )
            except urllib.error.HTTPError as exc:
                logger.warning(
                    "HttpEmitter: HTTP %d for event %s (attempt %d/%d): %s",
                    exc.code,
                    event.get("event_id", "?"),
                    attempt,
                    _MAX_RETRIES,
                    exc.reason,
                )
                # 4xx errors are not retryable
                if 400 <= exc.code < 500:
                    break
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                logger.warning(
                    "HttpEmitter: network error for event %s (attempt %d/%d): %s",
                    event.get("event_id", "?"),
                    attempt,
                    _MAX_RETRIES,
                    exc,
                )

            if attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.debug("HttpEmitter: retrying in %.1fs …", delay)
                time.sleep(delay)

        # All attempts failed — write to local buffer
        self._buffer.append(event)
        self._buffered += 1
        logger.info(
            "HttpEmitter: event %s buffered locally (total buffered: %d)",
            event.get("event_id", "?"),
            self._buffered,
        )
        return False

    # ------------------------------------------------------------------
    # Buffer flush
    # ------------------------------------------------------------------

    def flush_buffer(self) -> int:
        """Try to deliver all locally buffered events.

        Returns the number of events successfully flushed.
        """
        events = self._buffer.drain()
        if not events:
            return 0

        logger.info("HttpEmitter: flushing %d buffered events …", len(events))
        flushed = 0
        failed = 0

        for event in events:
            if self.emit(event):
                flushed += 1
            else:
                failed += 1

        logger.info(
            "HttpEmitter: flushed %d/%d buffered events (%d still queued)",
            flushed,
            len(events),
            failed,
        )
        return flushed

    # ------------------------------------------------------------------
    # Heartbeat (fire-and-forget)
    # ------------------------------------------------------------------

    def heartbeat(self, hostname: str, interval_seconds: int = 0) -> bool:
        """Send a heartbeat to POST /endpoints/heartbeat."""
        url = f"{self._api_url}/endpoints/heartbeat"
        payload = json.dumps(
            {"hostname": hostname, "interval_seconds": interval_seconds},
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "X-Api-Key": self._api_key,
                },
            )
            with urllib.request.urlopen(req, timeout=self._timeout, context=self._ssl_ctx) as resp:
                ok = resp.status in (200, 201, 202)
                if not ok:
                    logger.warning("HttpEmitter: heartbeat returned HTTP %d", resp.status)
                return ok
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            logger.debug("HttpEmitter: heartbeat failed (server unreachable): %s", exc)
            return False

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict[str, int]:
        return {
            "sent": self._sent,
            "buffered": self._buffered,
            "buffer_size": self._buffer.size(),
        }
