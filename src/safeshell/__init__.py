"""
Top-level facade for Safeshell.
"""

from safeshell.core import BaseSandbox
from safeshell.errors import ConfigurationError, SafeShellError
from safeshell.sandbox.native import NativeSandbox
from safeshell.types import CommandResult, NetworkAllowlist, NetworkMode

def Sandbox(
    cwd: str,
    *,
    network: NetworkMode = NetworkMode.BLOCKED,
    allowlist: NetworkAllowlist | None = None,
    timeout: float = 30.0,
) -> BaseSandbox:
    """
    Create a sandbox instance.
    Uses NativeSandbox (Seatbelt on macOS, Landlock on Linux).
    """
    return NativeSandbox(cwd, timeout=timeout, network=network, allowlist=allowlist)

__all__ = [
    "BaseSandbox",
    "CommandResult",
    "ConfigurationError",
    "NativeSandbox",
    "NetworkAllowlist",
    "NetworkMode",
    "SafeShellError",
    "Sandbox",
]
