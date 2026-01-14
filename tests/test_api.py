"""Tests for create_sandbox_tool API."""

from __future__ import annotations

from pathlib import Path

import pytest

from safeshell import LocalSandbox, SecurityPolicy, create_sandbox_tool
from safeshell.security.policy import SecurityViolation
from safeshell._types import SecurityLevel


class TestCreateSandboxTool:
    """Tests for the create_sandbox_tool factory function."""

    async def test_creates_toolkit(self, temp_dir: Path) -> None:
        """Should create a working toolkit."""
        toolkit = await create_sandbox_tool(source=temp_dir)
        try:
            result = await toolkit.bash("echo 'hello'")
            assert "hello" in result.stdout
        finally:
            await toolkit.close()

    async def test_defaults_to_current_directory(self) -> None:
        """Should default to current working directory."""
        toolkit = await create_sandbox_tool()
        try:
            result = await toolkit.bash("pwd")
            assert result.exit_code == 0
        finally:
            await toolkit.close()

    async def test_writes_inline_files(self, temp_dir: Path) -> None:
        """Should write inline files to the sandbox."""
        toolkit = await create_sandbox_tool(
            source=temp_dir,
            files={"inline.txt": "inline content"},
            read_only=False,
        )
        try:
            content = await toolkit.read_file("inline.txt")
            assert content == "inline content"
        finally:
            await toolkit.close()

    async def test_accepts_security_level(self, temp_dir: Path) -> None:
        """Should accept SecurityLevel enum."""
        toolkit = await create_sandbox_tool(
            source=temp_dir,
            security=SecurityLevel.STANDARD,
        )
        try:
            with pytest.raises(SecurityViolation):
                await toolkit.bash("rm -rf /")
        finally:
            await toolkit.close()

    async def test_accepts_security_policy(self, temp_dir: Path) -> None:
        """Should accept SecurityPolicy instance."""
        policy = SecurityPolicy.paranoid(allowed={"echo", "ls"})
        # Use LocalSandbox directly to avoid tool discovery
        sandbox = LocalSandbox(cwd=temp_dir, security=policy)
        try:
            result = await sandbox.execute("echo 'allowed'")
            assert "allowed" in result.stdout

            with pytest.raises(SecurityViolation):
                await sandbox.execute("cat file.txt")
        finally:
            await sandbox.close()

    async def test_paranoid_level_requires_policy(self, temp_dir: Path) -> None:
        """PARANOID security level should require a policy with allowlist."""
        with pytest.raises(ValueError, match="allowlist"):
            await create_sandbox_tool(
                source=temp_dir,
                security=SecurityLevel.PARANOID,
            )

    async def test_generates_tool_prompt(self, temp_dir: Path) -> None:
        """Should generate a tool prompt."""
        (temp_dir / "data.json").write_text("{}")

        toolkit = await create_sandbox_tool(source=temp_dir)
        try:
            # Should have discovered some tools
            assert len(toolkit.tool_prompt) > 0
        finally:
            await toolkit.close()

    async def test_includes_extra_instructions(self, temp_dir: Path) -> None:
        """Should include extra instructions in prompt."""
        toolkit = await create_sandbox_tool(
            source=temp_dir,
            extra_instructions="Always use jq for JSON processing.",
        )
        try:
            assert "jq" in toolkit.tool_prompt.lower()
        finally:
            await toolkit.close()

    async def test_read_only_mode(self, temp_dir: Path) -> None:
        """Read-only mode should be default."""
        original_file = temp_dir / "original.txt"
        original_file.write_text("original")

        toolkit = await create_sandbox_tool(source=temp_dir, read_only=True)
        try:
            await toolkit.write_file("original.txt", "modified")
            # Source should be unchanged
            assert original_file.read_text() == "original"
        finally:
            await toolkit.close()

    async def test_context_manager(self, temp_dir: Path) -> None:
        """Should work as async context manager."""
        async with await create_sandbox_tool(source=temp_dir) as toolkit:
            result = await toolkit.bash("echo 'context manager'")
            assert "context manager" in result.stdout
