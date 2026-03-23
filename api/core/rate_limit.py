"""Shared rate limiter for the API. Disabled when TESTING=1."""

import os
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["300/minute"],
    enabled=not os.environ.get("TESTING"),
)
