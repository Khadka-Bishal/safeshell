"""Pytest configuration and fixtures for py-sandbox tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio

from safeshell import LocalSandbox, SecurityPolicy, create_sandbox_tool
from safeshell._types import SandboxToolkit


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory(prefix="safeshell_test_") as tmp:
        yield Path(tmp)


@pytest_asyncio.fixture
async def sandbox(temp_dir: Path) -> AsyncGenerator[LocalSandbox, None]:
    """Create a LocalSandbox for testing."""
    # Create some test files
    (temp_dir / "test.txt").write_text("hello world")
    (temp_dir / "data.json").write_text('{"key": "value"}')

    sandbox = LocalSandbox(cwd=temp_dir, read_only=False)
    try:
        yield sandbox
    finally:
        await sandbox.close()


@pytest_asyncio.fixture
async def toolkit(temp_dir: Path) -> AsyncGenerator[SandboxToolkit, None]:
    """Create a SandboxToolkit for testing."""
    # Create some test files
    (temp_dir / "test.txt").write_text("hello world")

    toolkit = await create_sandbox_tool(source=temp_dir, read_only=False)
    try:
        yield toolkit
    finally:
        await toolkit.close()


@pytest.fixture
def standard_policy() -> SecurityPolicy:
    """Create a standard security policy."""
    return SecurityPolicy.standard()


@pytest.fixture
def paranoid_policy() -> SecurityPolicy:
    """Create a paranoid security policy with basic commands."""
    return SecurityPolicy.paranoid(allowed={"ls", "cat", "echo", "grep"})

