"""
Core type definitions for py-sandbox.

Uses dataclasses and Protocols for lightweight, typed abstractions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from safeshell.sandbox._base import Sandbox
    from safeshell.security.policy import SecurityPolicy


class SecurityLevel(Enum):
    """Security posture for the sandbox."""

    PERMISSIVE = "permissive"  # Log dangerous commands, don't block
    STANDARD = "standard"  # Block known-dangerous patterns
    PARANOID = "paranoid"  # Allowlist-only, deny by default


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Immutable result from command execution."""

    stdout: str
    stderr: str
    exit_code: int
    truncated: bool = False

    @property
    def success(self) -> bool:
        """Return True if command exited with code 0."""
        return self.exit_code == 0

    def raise_for_status(self) -> None:
        """Raise CommandError if exit_code is non-zero."""
        if not self.success:
            raise CommandError(
                f"Command failed with exit code {self.exit_code}: {self.stderr or self.stdout}"
            )


class CommandError(Exception):
    """Raised when a command exits with non-zero status."""

    pass


class BeforeExecuteHook(Protocol):
    """Hook called before command execution. Return modified command or raise to block."""

    def __call__(self, command: str) -> str: ...


class AfterExecuteHook(Protocol):
    """Hook called after command execution. Can modify result."""

    def __call__(self, command: str, result: CommandResult) -> CommandResult: ...


@dataclass
class SandboxToolkit:
    """
    Toolkit returned by create_sandbox_tool(), containing tools for AI agents.

    Attributes:
        sandbox: The underlying sandbox instance.
        tool_prompt: Generated prompt describing available tools for the LLM.
        security: The security policy in effect.
    """

    sandbox: Sandbox
    tool_prompt: str
    security: SecurityPolicy

    async def bash(self, command: str, *, timeout: float = 30.0) -> CommandResult:
        """Execute a bash command in the sandbox."""
        return await self.sandbox.execute(command, timeout=timeout)

    async def read_file(self, path: str) -> str:
        """Read a file from the sandbox filesystem."""
        return await self.sandbox.read_file(path)

    async def write_file(self, path: str, content: str | bytes) -> None:
        """Write a file to the sandbox filesystem."""
        await self.sandbox.write_file(path, content)

    async def close(self) -> None:
        """Clean up sandbox resources."""
        await self.sandbox.close()

    async def __aenter__(self) -> SandboxToolkit:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
