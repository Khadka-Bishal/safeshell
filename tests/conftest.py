"""Pytest configuration for safeshell tests."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio

from safeshell import NativeSandbox as LocalSandbox


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory(prefix="safeshell_test_") as tmp:
        yield Path(tmp)


@pytest_asyncio.fixture
async def sandbox(temp_dir: Path) -> AsyncGenerator[LocalSandbox, None]:
    """Create a LocalSandbox for testing."""
    (temp_dir / "test.txt").write_text("hello world")

    # NativeSandbox requires string or Path
    async with LocalSandbox(cwd=temp_dir) as sb:
        yield sb
