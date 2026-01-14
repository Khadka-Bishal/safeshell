"""LangChain integration for safeshell."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from safeshell._types import SandboxToolkit

HAS_LANGCHAIN = False
_StructuredTool: Any = None

try:
    import langchain_core.tools

    _StructuredTool = langchain_core.tools.StructuredTool
    HAS_LANGCHAIN = True
except ImportError:
    pass


def create_langchain_tools(toolkit: SandboxToolkit) -> dict[str, Any]:
    """
    Create LangChain tools from a SandboxToolkit.

    Args:
        toolkit: The sandbox toolkit to wrap.

    Returns:
        Dictionary of LangChain StructuredTool instances.

    Raises:
        ImportError: If langchain-core is not installed.

    Example:
        >>> toolkit = await create_sandbox_tool(source=".")
        >>> tools = create_langchain_tools(toolkit)
        >>> agent = create_react_agent(llm, list(tools.values()))
    """
    if not HAS_LANGCHAIN:
        raise ImportError(
            "LangChain integration requires langchain-core. "
            "Install with: pip install safeshell[langchain]"
        )

    import asyncio

    def run_bash(command: str) -> str:
        """Execute a bash command in the sandbox."""
        result = asyncio.get_event_loop().run_until_complete(toolkit.bash(command))
        if result.stderr and not result.success:
            return f"Error (exit {result.exit_code}): {result.stderr}"
        return result.stdout

    def read_file(path: str) -> str:
        """Read a file from the sandbox."""
        return asyncio.get_event_loop().run_until_complete(toolkit.read_file(path))

    def write_file(path: str, content: str) -> str:
        """Write a file to the sandbox."""
        asyncio.get_event_loop().run_until_complete(toolkit.write_file(path, content))
        return f"Written to {path}"

    bash_tool = _StructuredTool.from_function(
        func=run_bash,
        name="bash",
        description=f"Execute bash commands. {toolkit.tool_prompt}",
    )

    read_tool = _StructuredTool.from_function(
        func=read_file,
        name="read_file",
        description="Read a file from the sandbox filesystem.",
    )

    write_tool = _StructuredTool.from_function(
        func=write_file,
        name="write_file",
        description="Write content to a file in the sandbox.",
    )

    return {
        "bash": bash_tool,
        "read_file": read_tool,
        "write_file": write_tool,
    }
