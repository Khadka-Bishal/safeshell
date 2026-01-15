"""
Linux Landlock + network namespace isolation.

Uses kernel-level restrictions:
- Landlock for filesystem access control
- unshare --net for network isolation
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path


def is_landlock_available() -> bool:
    """Check if Landlock is available (Linux 5.13+)."""
    if platform.system() != "Linux":
        return False

    try:
        release = platform.release().split(".")
        major, minor = int(release[0]), int(release[1].split("-")[0])
        return major > 5 or (major == 5 and minor >= 13)
    except (IndexError, ValueError):
        return False


def supports_namespaces() -> bool:
    """
    Check if user namespaces are supported/allowed in this environment.
    Many CI/Docker environments block unshare.
    """
    if platform.system() != "Linux":
        return False

    try:
        # Try to run a dummy command in a new user namespace
        result = subprocess.run(
            ["unshare", "--user", "--map-root-user", "true"],
            capture_output=True,
            check=False
        )
        return result.returncode == 0
    except (FileNotFoundError, PermissionError, OSError):
        return False


def build_isolated_command(
    command: str,
    _workspace: Path,
    allow_network: bool = False,
) -> list[str]:
    """
    Wrap command with Linux isolation.

    Uses unshare for network namespace isolation.
    Landlock filesystem restrictions would require a C extension
    or the landlock Python package - for now we use unshare.

    Args:
        command: Shell command to run.
        _workspace: Working directory.
        allow_network: If True, skip network isolation.

    Returns:
        Command list for subprocess.
    """
    args = ["unshare", "--user", "--map-root-user"]

    if not allow_network:
        args.append("--net")  # New network namespace (no network)

    args.extend(["--", "bash", "-c", command])
    return args
