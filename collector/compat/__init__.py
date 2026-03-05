"""Cross-platform abstraction layer for process, network, and identity queries.

Scanners import from this package instead of calling Unix-specific tools
(pgrep, ps, lsof, codesign, etc.) directly.
"""

from .identity import (
    get_app_version,
    get_credential_store_entry,
    user_exists,
    verify_code_signature,
)
from .network import get_connections, get_listeners
from .paths import get_tool_paths
from .processes import find_processes, get_child_pids, get_process_info
from .services import get_service
from .types import (
    ConnectionInfo,
    ProcessInfo,
    ServiceInfo,
    SignatureInfo,
    ToolPaths,
)

__all__ = [
    "find_processes",
    "get_child_pids",
    "get_connections",
    "get_credential_store_entry",
    "get_app_version",
    "get_listeners",
    "get_process_info",
    "get_service",
    "get_tool_paths",
    "user_exists",
    "verify_code_signature",
    "ConnectionInfo",
    "ProcessInfo",
    "ServiceInfo",
    "SignatureInfo",
    "ToolPaths",
]
