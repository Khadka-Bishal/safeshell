"""
LangChain integration for safeshell.

Provides a ShellTool that wraps the Sandbox for safe execution.
"""

from __future__ import annotations

from typing import Any

try:
    from langchain_core.tools import BaseTool
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError(
        "LangChain integration requires 'langchain-core'. "
        "Install with `pip install safeshell[langchain]`"
    )

from safeshell import NetworkAllowlist, NetworkMode, Sandbox


class ShellToolInput(BaseModel):
    """Input for ShellTool."""

    command: str = Field(
        ...,
        description="The shell command to execute. "
        "Can be any valid shell command allowed by the policy.",
    )


class ShellTool(BaseTool):
    """
    Safe shell execution tool for LangChain agents.

    Wraps safeshell's Sandbox to provide secure command execution.
    Auto-detects Docker/Seatbelt/Landlock isolation.
    """

    name: str = "safe_shell"
    description: str = (
        "Execute shell commands safely. "
        "Use this for any task requiring code execution, file manipulation, "
        "or package installation. "
        "Blocked operations will return a permission error."
    )
    args_schema: type[BaseModel] = ShellToolInput

    # Configuration
    cwd: str = Field(default=".", description="Working directory")
    network: NetworkMode = Field(
        default=NetworkMode.BLOCKED, description="Network mode"
    )
    allowlist: NetworkAllowlist | None = Field(
        default=None, description="Network allowlist (if mode is ALLOWLIST)"
    )
    timeout: float = Field(default=30.0, description="Command timeout in seconds")

    def _run(self, command: str, run_manager: Any = None) -> str:
        """Synchronous run - not supported for async sandbox."""
        raise NotImplementedError(
            "ShellTool only supports async execution. "
            "Use `await tool.arun(command)` instead."
        )

    async def _arun(self, command: str, run_manager: Any = None) -> str:
        """
        Execute the command asynchronously in the sandbox.
        """
        try:
            async with Sandbox(
                cwd=self.cwd,
                network=self.network,
                allowlist=self.allowlist,
            ) as sandbox:
                result = await sandbox.execute(command, timeout=self.timeout)

                if result.exit_code != 0:
                    return f"Error (Exit Code {result.exit_code}):\n{result.stderr}"

                return result.stdout

        except Exception as e:
            return f"Execution Error: {e!s}"
