"""
Sandbox backends.
"""

from safeshell.sandbox.native import NativeSandbox, KernelIsolation
from safeshell.sandbox.docker import DockerSandbox, DockerConfig

__all__ = [
    "NativeSandbox", 
    "KernelIsolation",
    "DockerSandbox", 
    "DockerConfig"
]
