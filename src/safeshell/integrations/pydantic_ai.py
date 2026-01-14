"""
PydanticAI integration for safeshell.

Provides helpers to create PydanticAI-compatible tools.
"""

from __future__ import annotations

from typing import Callable

try:
    from pydantic_ai import RunContext, Tool
except ImportError:
    raise ImportError(
        "PydanticAI integration requires 'pydantic-ai'. "
        "Install with `pip install safeshell[pydantic-ai]`"
    )

from safeshell import NetworkAllowlist, NetworkMode, Sandbox


def create_shell_tool(
    cwd: str = ".",
    network: NetworkMode = NetworkMode.BLOCKED,
    allowlist: NetworkAllowlist | None = None,
    timeout: float = 30.0,
) -> Callable:
    """
    Create a PydanticAI tool function for safe shell execution.

    Returns a function decorated with @tool (implicitly or explicitly handled by PydanticAI)
    that can be registered with an Agent.

    Example:
        >>> from pydantic_ai import Agent
        >>> shell_tool = create_shell_tool("./project")
        >>> agent = Agent("openai:gpt-4", tools=[shell_tool])
    """

    async def shell_tool(
        ctx: RunContext, 
        command: str,
    ) -> str:
        """
        Execute a shell command safely. 
        Only allowed operations will succeed.
        """
        async with Sandbox(
            cwd=cwd,
            network=network,
            allowlist=allowlist,
        ) as sandbox:
            result = await sandbox.execute(command, timeout=timeout)
            
            if result.exit_code != 0:
                return f"Error (Exit Code {result.exit_code}):\n{result.stderr}"
            
            return result.stdout

    return shell_tool
