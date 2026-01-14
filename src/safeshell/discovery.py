"""
Dynamic tool discovery and LLM prompt generation.

Scans the sandbox to determine which tools are available and generates
prompts that help the LLM use the right tools for the job.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from safeshell.sandbox._base import Sandbox

# Known tools with their descriptions for LLM prompting
KNOWN_TOOLS: dict[str, str] = {
    # Search and filter
    "grep": "Pattern matching and searching (regex support)",
    "find": "Locate files by pattern, name, or attributes",
    "ag": "The Silver Searcher - fast code search",
    "rg": "ripgrep - fast regex search",
    # Text processing
    "sed": "Stream editor for substitution and transformation",
    "awk": "Field-based processing and pattern scanning",
    "cut": "Extract columns/fields by delimiter",
    "tr": "Translate, squeeze, or delete characters",
    "sort": "Sort lines alphabetically/numerically",
    "uniq": "Remove duplicates or count occurrences",
    # File viewing
    "cat": "View file contents",
    "head": "View first N lines of a file",
    "tail": "View last N lines of a file",
    "less": "Page through file contents",
    "wc": "Count lines, words, characters",
    # Structured data
    "jq": "Parse and manipulate JSON",
    "yq": "Parse YAML, XML, TOML",
    "xsv": "Fast CSV processing",
    "mlr": "Miller - CSV/JSON processing",
    # Comparison
    "diff": "Compare files line by line",
    "comm": "Compare two sorted files",
    # Network
    "curl": "Transfer data from URLs",
    "wget": "Download files from URLs",
    # Programming
    "python3": "Python interpreter",
    "python": "Python interpreter",
    "node": "Node.js runtime",
    # Utilities
    "xargs": "Build commands from stdin",
    "tee": "Split output to file and stdout",
    "ls": "List directory contents",
    "tree": "Display directory tree",
    "file": "Determine file type",
    "stat": "Display file status",
}

# Format-specific tool recommendations
FORMAT_TOOL_HINTS: dict[str, list[str]] = {
    ".json": ["jq", "python3 -c 'import json...'"],
    ".jsonl": ["jq -c", "python3"],
    ".yaml": ["yq"],
    ".yml": ["yq"],
    ".csv": ["awk", "cut", "xsv", "mlr", "python3 -c 'import csv...'"],
    ".tsv": ["awk", "cut"],
    ".xml": ["yq -p xml", "grep"],
    ".html": ["grep", "python3 -c 'from bs4...'"],
    ".md": ["grep", "cat"],
    ".py": ["grep", "ast module via python3"],
    ".js": ["grep", "node"],
    ".ts": ["grep"],
}


async def discover_tools(sandbox: Sandbox) -> set[str]:
    """
    Discover which tools are available in the sandbox.

    Uses `which` to check for the presence of known tools.

    Args:
        sandbox: The sandbox to check.

    Returns:
        Set of available tool names.
    """
    # Build a single command to check all tools at once
    tool_names = list(KNOWN_TOOLS.keys())
    check_command = " ".join(f"which {tool} 2>/dev/null;" for tool in tool_names)

    result = await sandbox.execute(check_command, timeout=10.0)

    available: set[str] = set()
    for line in result.stdout.strip().split("\n"):
        if line and "/" in line:  # Valid path output
            tool_name = Path(line.strip()).name
            if tool_name in KNOWN_TOOLS:
                available.add(tool_name)

    return available


async def generate_tool_prompt(
    sandbox: Sandbox,
    files: list[str],
    *,
    extra_instructions: str | None = None,
) -> str:
    """
    Generate an LLM-optimized prompt describing available tools.

    The prompt includes:
    - List of available tools
    - Format-specific recommendations based on file extensions
    - Any extra instructions provided

    Args:
        sandbox: The sandbox to discover tools from.
        files: List of file paths available in the sandbox.
        extra_instructions: Additional context for the LLM.

    Returns:
        A formatted prompt string.
    """
    available = await discover_tools(sandbox)

    if not available:
        return extra_instructions or ""

    lines: list[str] = []

    # Core tools list
    core_tools = sorted(available & {"grep", "sed", "awk", "cat", "head", "tail", "find", "ls"})
    if core_tools:
        lines.append(f"Available tools: {', '.join(core_tools)}, and more")

    # Highlight special tools
    special_tools = []
    if "jq" in available:
        special_tools.append("jq for JSON")
    if "yq" in available:
        special_tools.append("yq for YAML/XML")
    if "rg" in available or "ag" in available:
        special_tools.append(f"{'rg' if 'rg' in available else 'ag'} for fast search")
    if special_tools:
        lines.append(f"Special: {', '.join(special_tools)}")

    # File format hints based on what's in the project
    extensions = {Path(f).suffix.lower() for f in files if "." in f}
    hints_added = set()

    for ext in sorted(extensions):
        if ext in FORMAT_TOOL_HINTS:
            # Filter to only available tools
            hints = []
            for hint in FORMAT_TOOL_HINTS[ext]:
                base_tool = hint.split()[0]
                if base_tool in available or "python" in hint.lower():
                    hints.append(hint)

            if hints and ext not in hints_added:
                lines.append(f"For {ext} files: {', '.join(hints[:2])}")
                hints_added.add(ext)

    # Extra instructions
    if extra_instructions:
        lines.append("")
        lines.append(extra_instructions)

    return "\n".join(lines)
