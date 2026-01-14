"""
Main entry point: create_sandbox_tool factory function.

This is the primary API for creating sandboxed tools for AI agents.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from safeshell._types import SandboxToolkit, SecurityLevel
from safeshell.discovery import generate_tool_prompt
from safeshell.sandbox.local import LocalSandbox
from safeshell.security.policy import SecurityPolicy

if TYPE_CHECKING:
    from safeshell.sandbox._base import Sandbox


async def create_sandbox_tool(
    *,
    source: Path | str | None = None,
    files: dict[str, str] | None = None,
    sandbox: Sandbox | Literal["local"] = "local",
    security: SecurityPolicy | SecurityLevel | None = None,
    read_only: bool = True,
    extra_instructions: str | None = None,
    max_output_bytes: int = 30_000,
) -> SandboxToolkit:
    """
    Create a sandboxed bash tool for AI agents.

    This is the main entry point for py-sandbox. It creates a toolkit
    with bash, read_file, and write_file capabilities, protected by
    a configurable security policy.

    Args:
        source: Local directory to make available in the sandbox.
                Defaults to current working directory.
        files: Inline files to write to the sandbox (path -> content).
        sandbox: Sandbox backend. Currently only "local" is supported.
                 Pass a Sandbox instance for custom implementations.
        security: Security policy or level. Defaults to STANDARD.
        read_only: If True, writes don't affect the source directory.
                   Uses a temporary overlay directory.
        extra_instructions: Additional context for the LLM prompt.
        max_output_bytes: Maximum bytes for stdout/stderr before truncation.

    Returns:
        SandboxToolkit with bash, read_file, and write_file methods.

    Example:
        >>> toolkit = await create_sandbox_tool(source="./my_project")
        >>> result = await toolkit.bash("ls -la")
        >>> print(result.stdout)

    Example with security levels:
        >>> # Paranoid mode - only allow specific commands
        >>> toolkit = await create_sandbox_tool(
        ...     source=".",
        ...     security=SecurityPolicy.paranoid(allowed={"ls", "cat", "grep"})
        ... )
    """
    # Resolve source directory
    source_path = Path(source).resolve() if source else Path.cwd()

    # Resolve security policy
    policy: SecurityPolicy
    if security is None:
        policy = SecurityPolicy.standard()
    elif isinstance(security, SecurityLevel):
        if security == SecurityLevel.PARANOID:
             raise ValueError(
                "SecurityLevel.PARANOID requires an allowlist. "
                "Use SecurityPolicy.paranoid(allowed={...}) instead."
            )
        policy = SecurityPolicy(level=security)
    else:
        policy = security

    # Create sandbox backend
    sandbox_instance: Sandbox
    if isinstance(sandbox, str):
        if sandbox == "local":
            sandbox_instance = LocalSandbox(
                cwd=source_path,
                security=policy,
                read_only=read_only,
                max_output_bytes=max_output_bytes,
            )
        else:
            raise ValueError(
                f"Unknown sandbox type: {sandbox}. Use 'local' or provide a Sandbox instance."
            )
    else:
        sandbox_instance = sandbox

    # Write inline files if provided
    if files:
        for path, content in files.items():
            await sandbox_instance.write_file(path, content)

    # Build file list for prompt generation
    file_list = list((files or {}).keys())
    if source_path.exists():
        try:
            # List files in source directory (limit to avoid overwhelming)
            for i, p in enumerate(source_path.rglob("*")):
                if i >= 1000:  # Limit file enumeration
                    break
                if p.is_file() and not any(part.startswith(".") for part in p.parts):
                    file_list.append(str(p.relative_to(source_path)))
        except PermissionError:
            pass  # Skip directories we can't read

    # Generate LLM tool prompt
    tool_prompt = await generate_tool_prompt(
        sandbox_instance,
        file_list,
        extra_instructions=extra_instructions,
    )

    return SandboxToolkit(
        sandbox=sandbox_instance,
        tool_prompt=tool_prompt,
        security=policy,
    )
