"""
Abstract base class for all sandbox implementations.

All sandbox backends (Local, Docker, E2B) implement this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from safeshell._types import CommandResult


class Sandbox(ABC):
    """
    Abstract base for all sandbox implementations.

    Provides a consistent interface for executing commands and
    managing files in an isolated environment.
    """

    @abstractmethod
    async def execute(self, command: str, *, timeout: float = 30.0) -> CommandResult:
        """
        Execute a bash command and return the result.

        Args:
            command: The bash command to execute.
            timeout: Maximum seconds to wait before killing the process.

        Returns:
            CommandResult with stdout, stderr, and exit_code.
        """
        ...

    @abstractmethod
    async def read_file(self, path: str | Path) -> str:
        """
        Read a file from the sandbox filesystem.

        Args:
            path: Path to the file (relative to sandbox working directory).

        Returns:
            File contents as a string.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        ...

    @abstractmethod
    async def write_file(self, path: str | Path, content: str | bytes) -> None:
        """
        Write a file to the sandbox filesystem.

        Creates parent directories if needed.

        Args:
            path: Path where the file should be written.
            content: Content to write (string or bytes).
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """
        Clean up sandbox resources.

        Should be called when done with the sandbox.
        Idempotent - safe to call multiple times.
        """
        ...

    async def __aenter__(self) -> Sandbox:
        """Enter async context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit async context manager, cleaning up resources."""
        await self.close()
