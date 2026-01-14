"""
Local subprocess-based sandbox implementation.

This is the default sandbox for local development. It uses asyncio.subprocess
for non-blocking execution with security controls.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from safeshell._types import CommandResult
from safeshell.sandbox._base import Sandbox

if TYPE_CHECKING:
    from safeshell.security.policy import SecurityPolicy


class LocalSandbox(Sandbox):
    """
    Subprocess-based sandbox for local development.

    Security features:
    - Command pattern blocking via SecurityPolicy
    - Timeout enforcement
    - Output truncation to prevent memory exhaustion
    - Optional read-only mode using a temporary overlay directory

    Example:
        >>> sandbox = LocalSandbox(cwd="./my_project")
        >>> result = await sandbox.execute("ls -la")
        >>> print(result.stdout)
    """

    def __init__(
        self,
        cwd: Path | str,
        *,
        security: SecurityPolicy | None = None,
        read_only: bool = False,
        env: dict[str, str] | None = None,
        max_output_bytes: int = 30_000,
    ) -> None:
        """
        Initialize a local sandbox.

        Args:
            cwd: Working directory for command execution.
            security: Security policy to enforce. Defaults to standard policy.
            read_only: If True, use a temp directory overlay for writes.
            env: Environment variables for subprocesses.
            max_output_bytes: Maximum bytes for stdout/stderr before truncation.
        """
        self._cwd = Path(cwd).resolve()
        self._read_only = read_only
        self._env = env
        self._max_output_bytes = max_output_bytes
        self._closed = False

        # Lazy import to avoid circular dependency
        from safeshell.security.policy import SecurityPolicy

        self._security = security or SecurityPolicy.standard()

        # For read-only mode, create a temp overlay directory
        self._overlay_dir: Path | None = None
        if read_only:
            self._overlay_dir = Path(tempfile.mkdtemp(prefix="safeshell_"))
            # Copy source to overlay for read-write operations
            shutil.copytree(self._cwd, self._overlay_dir / "workspace", dirs_exist_ok=True)

    @property
    def effective_cwd(self) -> Path:
        """Return the effective working directory (overlay if read-only)."""
        if self._overlay_dir:
            return self._overlay_dir / "workspace"
        return self._cwd

    async def execute(self, command: str, *, timeout: float = 30.0) -> CommandResult:
        """
        Execute a bash command in the sandbox.

        Args:
            command: The bash command to execute.
            timeout: Maximum seconds to wait before killing the process.

        Returns:
            CommandResult with stdout, stderr, and exit_code.

        Raises:
            SecurityViolation: If the command violates the security policy.
        """
        if self._closed:
            raise RuntimeError("Sandbox has been closed")

        # Security check - may raise SecurityViolation
        command = self._security.check_command(command)

        # Create subprocess with shell=True for bash compatibility
        # Security: we rely on SecurityPolicy to block dangerous patterns
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=self.effective_cwd,
            env=self._env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()  # Ensure process is reaped
            return CommandResult(
                stdout="",
                stderr=f"Command timed out after {timeout}s",
                exit_code=-1,
                truncated=False,
            )

        # Decode and truncate output
        stdout, stdout_truncated = self._decode_and_truncate(stdout_bytes)
        stderr, stderr_truncated = self._decode_and_truncate(stderr_bytes)

        result = CommandResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=proc.returncode or 0,
            truncated=stdout_truncated or stderr_truncated,
        )

        return result

    def _decode_and_truncate(self, data: bytes) -> tuple[str, bool]:
        """Decode bytes and truncate if too large."""
        text = data.decode("utf-8", errors="replace")
        if len(text) > self._max_output_bytes:
            truncated_count = len(text) - self._max_output_bytes
            text = text[: self._max_output_bytes]
            text += f"\n\n[Truncated: {truncated_count} characters removed]"
            return text, True
        return text, False

    async def read_file(self, path: str | Path) -> str:
        """
        Read a file from the sandbox filesystem.

        Args:
            path: Path to the file (relative to working directory).

        Returns:
            File contents as a string.

        Raises:
            FileNotFoundError: If the file doesn't exist.
        """
        if self._closed:
            raise RuntimeError("Sandbox has been closed")

        file_path = self.effective_cwd / path
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        return file_path.read_text(encoding="utf-8")

    async def write_file(self, path: str | Path, content: str | bytes) -> None:
        """
        Write a file to the sandbox filesystem.

        Creates parent directories if needed.

        Args:
            path: Path where the file should be written.
            content: Content to write (string or bytes).
        """
        if self._closed:
            raise RuntimeError("Sandbox has been closed")

        file_path = self.effective_cwd / path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, str):
            file_path.write_text(content, encoding="utf-8")
        else:
            file_path.write_bytes(content)

    async def close(self) -> None:
        """
        Clean up sandbox resources.

        Removes the overlay directory if read-only mode was used.
        Safe to call multiple times.
        """
        if self._closed:
            return

        self._closed = True

        # Clean up overlay directory
        if self._overlay_dir and self._overlay_dir.exists():
            shutil.rmtree(self._overlay_dir, ignore_errors=True)
            self._overlay_dir = None
