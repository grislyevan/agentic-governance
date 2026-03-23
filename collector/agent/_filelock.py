"""Cross-platform advisory file locking.

Uses fcntl on Unix and msvcrt on Windows so that StateDiffer and
LocalBuffer work on all supported platforms.
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Iterator

if sys.platform == "win32":
    import msvcrt

    @contextmanager
    def file_lock(lock_path: str) -> Iterator[None]:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            yield
        finally:
            try:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            os.close(fd)

else:
    import fcntl

    @contextmanager
    def file_lock(lock_path: str) -> Iterator[None]:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
