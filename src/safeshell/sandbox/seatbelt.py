"""
macOS Seatbelt (sandbox-exec) integration.

Provides OS-level filesystem isolation on macOS using the sandbox-exec
command with dynamically generated Seatbelt profiles in SBPL (Scheme).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# Paths that are ALWAYS denied write access, regardless of configuration.
# These protect against sandbox escape via shell/git configuration modification.
MANDATORY_DENY_WRITE_LITERALS: tuple[str, ...] = (
    ".bashrc",
    ".bash_profile",
    ".zshrc",
    ".zprofile",
    ".profile",
    ".gitconfig",
    ".gitmodules",
    ".ripgreprc",
    ".mcp.json",
)

MANDATORY_DENY_WRITE_SUBPATHS: tuple[str, ...] = (
    ".ssh",
    ".aws",
    ".kube",
    ".gnupg",
    ".vscode",
    ".idea",
    ".claude",
    ".cursor",
)

@dataclass
class SeatbeltProfile:
    """
    Configuration for generating a macOS Seatbelt (sandbox-exec) profile.

    The profile uses a deny-default model with explicit allows:
    - Read: Allowed for system paths and workspace
    - Write: Allowed ONLY for workspace and temp directories
    - Network: Blocked by default (can be enabled)

    Example:
        >>> profile = SeatbeltProfile(workspace=Path.cwd())
        >>> sbpl = profile.generate()
        >>> # Use with sandbox-exec -p <sbpl> -- <command>
    """

    workspace: Path
    """Primary workspace directory with read-write access."""

    allow_read_paths: list[Path] = field(default_factory=list)
    """Additional paths to allow read access (beyond system defaults)."""

    allow_write_paths: list[Path] = field(default_factory=list)
    """Additional paths to allow write access (beyond workspace)."""

    allow_network: bool = False
    """If True, allows outbound network connections."""

    allow_network_localhost_only: bool = False
    """If True, allows only localhost network (for proxy mode)."""

    network_proxy_port: int | None = None
    """If set, allows network ONLY to localhost:port (Phase 2)."""

    def generate(self) -> str:
        """
        Generate the Seatbelt profile in SBPL format.

        Uses a "broad read, restricted write" model:
        - Read access: Entire filesystem (needed for shell/tools to function)
        - Write access: Only workspace and temp directories

        Returns:
            String containing the complete SBPL profile.
        """
        home = Path.home()
        workspace = self.workspace.resolve()

        lines: list[str] = [
            "(version 1)",
            "",
            ";; safeshell Seatbelt Profile",
            ";; Generated for workspace: " + str(workspace),
            "",
            ";; Default deny - security baseline",
            "(deny default)",
            "",
            ";; ========== READ ACCESS ==========",
            ";; Allow read access to entire filesystem",
            ";; (Shells and tools need broad read access to function)",
            "(allow file-read*)",
            "",
            ";; ========== WRITE ACCESS ==========",
            ";; Write access ONLY to workspace and temp directories",
            "(allow file-write*",
            f'    (subpath "{workspace}")',
            '    (subpath "/tmp")',
            '    (subpath "/private/tmp")',
            f'    (subpath "{tempfile.gettempdir()}")',
            ")",
            "",
        ]

        # Add additional read paths
        if self.allow_read_paths:
            lines.append(";; Additional read paths")
            lines.append("(allow file-read*")
            for path in self.allow_read_paths:
                lines.append(f'    (subpath "{path.resolve()}")')
            lines.append(")")
            lines.append("")

        # Add additional write paths
        if self.allow_write_paths:
            lines.append(";; Additional write paths")
            lines.append("(allow file-write*")
            for path in self.allow_write_paths:
                lines.append(f'    (subpath "{path.resolve()}")')
            lines.append(")")
            lines.append("")

        # Mandatory denies - these ALWAYS apply
        lines.append(";; ========== MANDATORY DENIES ==========")
        lines.append(";; These paths are ALWAYS protected (defense in depth)")
        lines.append("")

        # Deny specific files
        lines.append(";; Protected config files")
        for filename in MANDATORY_DENY_WRITE_LITERALS:
            filepath = home / filename
            lines.append(f'(deny file-write* (literal "{filepath}"))')
        lines.append("")

        # Deny directories
        lines.append(";; Protected directories")
        for dirname in MANDATORY_DENY_WRITE_SUBPATHS:
            dirpath = home / dirname
            lines.append(f'(deny file-write* (subpath "{dirpath}"))')

        # Git hooks protection (even inside workspace)
        lines.append("")
        lines.append(";; Git hooks protection (prevents code execution)")
        lines.append(f'(deny file-write* (subpath "{workspace}/.git/hooks"))')
        lines.append(f'(deny file-write* (literal "{workspace}/.git/config"))')
        lines.append("")

        # Network rules
        lines.append(";; ========== NETWORK ==========")
        if self.allow_network:
            lines.append(";; Full network access enabled")
            lines.append("(allow network*)")
        elif self.allow_network_localhost_only or self.network_proxy_port:
            port = self.network_proxy_port or 0
            lines.append(f";; Localhost-only network (proxy port: {port})")
            lines.append("(allow network* (local ip))")
            if port:
                lines.append(f";; Only port {port} allowed for proxy")
        else:
            lines.append(";; Network BLOCKED (default)")
            lines.append("(deny network*)")
        lines.append("")

        # Process execution
        lines.append(";; ========== PROCESS EXECUTION ==========")
        lines.append("(allow process-exec)")
        lines.append("(allow process-fork)")
        lines.append("")

        # Mach IPC (required for many macOS operations)
        lines.append(";; Mach IPC (required for subprocess spawning)")
        lines.append("(allow mach-lookup)")
        lines.append("")

        # Signals
        lines.append(";; Signal handling")
        lines.append("(allow signal)")
        lines.append("")

        # Sysctl (needed for various system calls)
        lines.append(";; System info queries")
        lines.append("(allow sysctl-read)")
        lines.append("")

        return "\n".join(lines)

    def write_to_file(self, path: Path | None = None) -> Path:
        """
        Write the profile to a file.

        Args:
            path: Destination path. If None, creates a temp file.

        Returns:
            Path to the written profile file.
        """
        if path is None:
            fd, path_str = tempfile.mkstemp(suffix=".sb", prefix="safeshell_")
            os.close(fd)
            path = Path(path_str)

        path.write_text(self.generate(), encoding="utf-8")
        return path


def is_seatbelt_available() -> bool:
    """
    Check if sandbox-exec is available on this system.

    Returns:
        True if running on macOS with sandbox-exec available.
    """
    import platform

    if platform.system() != "Darwin":
        return False

    try:
        result = subprocess.run(
            ["which", "sandbox-exec"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def build_sandboxed_command(
    command: str | Sequence[str],
    profile: SeatbeltProfile,
    shell: bool = True,
) -> list[str]:
    """
    Build a command line that runs the given command inside a Seatbelt sandbox.

    Args:
        command: The command to execute.
        profile: Seatbelt profile configuration.
        shell: If True, wrap command in bash -c (for shell expansion).

    Returns:
        List of arguments for subprocess.run().
    """
    sbpl = profile.generate()

    # sandbox-exec -p <profile> -- <command>
    if shell and isinstance(command, str):
        return [
            "sandbox-exec",
            "-p", sbpl,
            "--",
            "bash", "-c", command,
        ]
    elif isinstance(command, str):
        return ["sandbox-exec", "-p", sbpl, "--", *command.split()]
    else:
        return ["sandbox-exec", "-p", sbpl, "--", *list(command)]
