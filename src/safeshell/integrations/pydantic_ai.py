"""PydanticAI integration for safeshell."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from safeshell._types import SandboxToolkit

try:
    import pydantic_ai  # noqa: F401

    HAS_PYDANTIC_AI = True
except ImportError:
    HAS_PYDANTIC_AI = False


def create_pydantic_ai_tools(toolkit: SandboxToolkit) -> list[Callable[..., Any]]:
    """
    Create PydanticAI tool functions from a SandboxToolkit.

    Args:
        toolkit: The sandbox toolkit to wrap.

    Returns:
        List of async functions that can be used as PydanticAI tools.

    Raises:
        ImportError: If pydantic-ai is not installed.

    Example:
        >>> toolkit = await create_sandbox_tool(source=".")
        >>> tools = create_pydantic_ai_tools(toolkit)
        >>> agent = Agent("openai:gpt-4", tools=tools)
    """
    if not HAS_PYDANTIC_AI:
        raise ImportError(
            "PydanticAI integration requires pydantic-ai. "
            "Install with: pip install safeshell[pydantic-ai]"
        )

    async def bash(command: str) -> str:
        """
        Execute a bash command in the sandbox.

        Args:
            command: The bash command to execute.

        Returns:
            Command output (stdout) or error message.
        """
        result = await toolkit.bash(command)
        if result.stderr and not result.success:
            return f"Error (exit {result.exit_code}): {result.stderr}"
        return result.stdout

    async def read_file(path: str) -> str:
        """
        Read a file from the sandbox.

        Args:
            path: Path to the file.

        Returns:
            File contents.
        """
        return await toolkit.read_file(path)

    async def write_file(path: str, content: str) -> str:
        """
        Write content to a file in the sandbox.

        Args:
            path: Path where to write.
            content: Content to write.

        Returns:
            Confirmation message.
        """
        await toolkit.write_file(path, content)
        return f"Written to {path}"

    # Add tool prompt as docstring enhancement
    bash.__doc__ = f"{bash.__doc__}\n\nAvailable tools: {toolkit.tool_prompt}"

    return [bash, read_file, write_file]
