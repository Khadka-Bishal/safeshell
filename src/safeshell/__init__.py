"""
safeshell: Secure, sandboxed shell access for AI agents.
"""

from safeshell._types import CommandResult, SecurityLevel
from safeshell.api import create_sandbox_tool
from safeshell.sandbox._base import Sandbox
from safeshell.sandbox.local import LocalSandbox
from safeshell.security.policy import SecurityPolicy, SecurityViolation

__all__ = [
    "CommandResult",
    "LocalSandbox",
    "Sandbox",
    "SecurityLevel",
    "SecurityPolicy",
    "SecurityViolation",
    "create_sandbox_tool",
]

__version__ = "0.1.1"
