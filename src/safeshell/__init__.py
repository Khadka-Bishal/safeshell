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

# Factory
def Sandbox(
    cwd: str, 
    *, 
    prefer_docker: bool = True,
    network: NetworkMode = NetworkMode.BLOCKED,
    allowlist: Optional[NetworkAllowlist] = None,
    timeout: float = 30.0
) -> BaseSandbox:
    """
    Create a sandbox instance, auto-detecting the best backend.
    """
    backend = None
    
    if prefer_docker:
        try:
            from safeshell.sandbox.docker import DockerSandbox, DockerConfig
            # Checking availability is usually done by instantiating or a check function
            # Here we assume if import works, let's try to verify docker presence
            import shutil
            if shutil.which("docker"):
                # Check for running daemon? For now assume existence implies availability
                return DockerSandbox(cwd, timeout=timeout, network=network)
        except ImportError:
            pass
        except Exception:
            pass # Fallback

    # Fallback to Native
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
