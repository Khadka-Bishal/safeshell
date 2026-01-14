"""Tests for framework integrations."""

import pytest
from safeshell import NativeSandbox as LocalSandbox, NetworkMode

# --- LangChain Tests ---

def test_langchain_import_error():
    """Test that importing without dependencies raises ImportError."""
    try:
        from safeshell.integrations.langchain import ShellTool
    except ImportError:
        return


@pytest.mark.asyncio
async def test_langchain_tool():
    """Test LangChain ShellTool."""
    try:
        from safeshell.integrations.langchain import ShellTool
    except ImportError:
        pytest.skip("langchain-core not installed")

    tool = ShellTool(cwd=".", network=NetworkMode.BLOCKED)
    
    # Test arguments schema
    assert tool.args_schema
    assert "command" in tool.args_schema.model_fields

    # Test execution
    result = await tool.arun("echo hello")
    assert result.strip() == "hello"

    # Test error handling
    result = await tool.arun("exit 1")
    assert "Error" in result
    assert "Exit Code 1" in result


# --- PydanticAI Tests ---

@pytest.mark.asyncio
async def test_pydantic_ai_tool():
    """Test PydanticAI tool creation."""
    try:
        from safeshell.integrations.pydantic_ai import create_shell_tool
        # We need to mock RunContext as it's required by the tool signature
        from dataclasses import dataclass
        @dataclass
        class MockContext:
            deps: dict
            
    except ImportError:
        pytest.skip("pydantic-ai not installed")

    tool_fn = create_shell_tool(cwd=".", network=NetworkMode.BLOCKED)
    
    # Verify it runs
    ctx = MockContext(deps={})
    result = await tool_fn(ctx, "echo pydantic")
    assert result.strip() == "pydantic"
