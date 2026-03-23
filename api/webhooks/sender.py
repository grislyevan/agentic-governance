"""HTTP delivery for webhook payloads with HMAC signing and retry."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import uuid
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # loopback
    ipaddress.ip_network("10.0.0.0/8"),         # RFC-1918
    ipaddress.ip_network("172.16.0.0/12"),      # RFC-1918
    ipaddress.ip_network("192.168.0.0/16"),     # RFC-1918
    ipaddress.ip_network("169.254.0.0/16"),     # link-local / AWS metadata
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
]

def _validate_webhook_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Webhook URL must use http or https, got: {parsed.scheme!r}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Webhook URL has no hostname")
    try:
        results = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve webhook hostname {hostname!r}: {exc}") from exc
    for _, _, _, _, sockaddr in results:
        ip = ipaddress.ip_address(sockaddr[0])
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                raise ValueError(
                    f"Webhook URL resolves to a blocked address ({ip}). "
                    "Only public IPs are allowed."
                )

MAX_RETRIES = 3
RETRY_DELAYS = [1, 4, 16]
TIMEOUT_SECONDS = 10


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for the payload."""
    return hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


async def deliver(
    url: str,
    secret: str,
    payload: dict[str, Any],
    extra_headers: dict[str, str] | None = None,
) -> bool:
    """POST a webhook payload to the given URL with HMAC signature.

    Retries up to MAX_RETRIES times with exponential backoff.
    Returns True on success (2xx), False on permanent failure.
    extra_headers are merged for SIEM auth (e.g. Splunk HEC, Elastic ApiKey).
    """
    try:
        _validate_webhook_url(url)
    except ValueError as e:
        logger.warning("Webhook delivery blocked due to invalid URL %s: %s", url, e)
        return False

    delivery_id = uuid.uuid4().hex
    payload_bytes = json.dumps(payload, default=str, sort_keys=True).encode()
    signature = _sign_payload(payload_bytes, secret)

    headers = {
        "Content-Type": "application/json",
        "X-Detec-Signature": f"sha256={signature}",
        "X-Detec-Delivery-Id": delivery_id,
        "User-Agent": "Detec-Webhook/1.0",
    }
    if extra_headers:
        headers = {**headers, **extra_headers}

    import asyncio

    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False) as client:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.post(url, content=payload_bytes, headers=headers)
                if 200 <= resp.status_code < 300:
                    logger.info(
                        "Webhook delivered: url=%s delivery_id=%s status=%d",
                        url, delivery_id, resp.status_code,
                    )
                    return True
                # Don't retry client errors (except 429 Too Many Requests)
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    logger.warning(
                        "Webhook delivery permanent failure: url=%s delivery_id=%s status=%d",
                        url, delivery_id, resp.status_code,
                    )
                    return False
                logger.warning(
                    "Webhook delivery failed: url=%s delivery_id=%s status=%d attempt=%d/%d",
                    url, delivery_id, resp.status_code, attempt + 1, MAX_RETRIES,
                )
            except Exception:
                logger.warning(
                    "Webhook delivery error: url=%s delivery_id=%s attempt=%d/%d",
                    url, delivery_id, attempt + 1, MAX_RETRIES,
                    exc_info=True,
                )

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(RETRY_DELAYS[attempt])

    logger.error("Webhook delivery permanently failed: url=%s delivery_id=%s", url, delivery_id)
    return False
