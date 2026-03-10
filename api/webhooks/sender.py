"""HTTP delivery for webhook payloads with HMAC signing and retry."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

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
) -> bool:
    """POST a webhook payload to the given URL with HMAC signature.

    Retries up to MAX_RETRIES times with exponential backoff.
    Returns True on success (2xx), False on permanent failure.
    """
    delivery_id = uuid.uuid4().hex
    payload_bytes = json.dumps(payload, default=str, sort_keys=True).encode()
    signature = _sign_payload(payload_bytes, secret)

    headers = {
        "Content-Type": "application/json",
        "X-Detec-Signature": f"sha256={signature}",
        "X-Detec-Delivery-Id": delivery_id,
        "User-Agent": "Detec-Webhook/1.0",
    }

    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.post(url, content=payload_bytes, headers=headers)
            if 200 <= resp.status_code < 300:
                logger.info(
                    "Webhook delivered: url=%s delivery_id=%s status=%d",
                    url, delivery_id, resp.status_code,
                )
                return True
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
            import asyncio
            await asyncio.sleep(RETRY_DELAYS[attempt])

    logger.error("Webhook delivery permanently failed: url=%s delivery_id=%s", url, delivery_id)
    return False
