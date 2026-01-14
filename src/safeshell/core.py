"""
Abstract base class for sandbox implementations.
Enforces consistent interface across Docker and Native backends.
"""

from __future__ import annotations

import abc
from pathlib import Path

from safeshell.types import CommandResult


class BaseSandbox(abc.ABC):
    """Interface for all sandbox implementations."""

    def __init__(self, cwd: str | Path, timeout: float = 30.0) -> None:
        self.cwd = Path(cwd).absolute()
        self.timeout = timeout
        self._closed = False

    @abc.abstractmethod
    async def execute(
        self,
        command: str,
        *,
        timeout: float | None = None
    ) -> CommandResult:
        """
        Execute a shell command.
        
        Args:
            command: Shell command string.
            timeout: Execution timeout in seconds.
            
        Returns:
            CommandResult with stdout/stderr/exit_code.
        """
        pass

    @abc.abstractmethod
    async def close(self) -> None:
        """Release resources."""
        pass

    async def __aenter__(self) -> BaseSandbox:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
