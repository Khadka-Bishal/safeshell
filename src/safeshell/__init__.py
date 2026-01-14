"""
Top-level facade for Safeshell.
"""

from warnings import warn
from typing import Optional

from safeshell.types import CommandResult
from safeshell.errors import SafeShellError, ConfigurationError
from safeshell.networking import NetworkMode, NetworkAllowlist
from safeshell.core import BaseSandbox
from safeshell.sandbox.native import NativeSandbox

def Sandbox(
    cwd: str, 
    *, 
    network: NetworkMode = NetworkMode.BLOCKED,
    allowlist: Optional[NetworkAllowlist] = None,
    timeout: float = 30.0
) -> BaseSandbox:
    """
    Create a sandbox instance.
    
    Uses NativeSandbox (Seatbelt on macOS, Landlock on Linux).
    """
    return NativeSandbox(cwd, timeout=timeout, network=network, allowlist=allowlist)


# Exports
__all__ = [
    "Sandbox",
    "BaseSandbox",
    "NativeSandbox",
    "CommandResult",
    "NetworkMode",
    "NetworkAllowlist",
    "SafeShellError",
    "ConfigurationError"
]
