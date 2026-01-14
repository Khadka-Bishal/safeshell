"""
Security policy with pattern-based command blocking.

This is the core security layer that protects against dangerous commands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from safeshell._types import SecurityLevel


class SecurityViolation(Exception):
    """
    Raised when a command violates the security policy.

    Attributes:
        command: The command that was blocked.
        reason: Why the command was blocked.
    """

    def __init__(self, reason: str, command: str = "") -> None:
        self.command = command
        self.reason = reason
        super().__init__(f"Security violation: {reason}")


# Dangerous command patterns - compiled regex with human-readable descriptions
DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Filesystem destruction
    (re.compile(r"\brm\s+(-[rf]+\s+)*[/~]"), "Recursive delete of root or home directory"),
    (re.compile(r"\brm\s+-[rf]*\s+-[rf]*\s+/"), "Recursive delete of root directory"),
    # Remote code execution
    (re.compile(r"\bcurl\b.*\|\s*(ba)?sh"), "Remote code execution via curl|sh"),
    (re.compile(r"\bwget\b.*\|\s*(ba)?sh"), "Remote code execution via wget|sh"),
    (re.compile(r"\bcurl\b.*\|\s*python"), "Remote code execution via curl|python"),
    (re.compile(r"\bwget\b.*\|\s*python"), "Remote code execution via wget|python"),
    # Fork bombs and resource exhaustion
    (re.compile(r":\s*\(\s*\)\s*\{.*\}"), "Fork bomb pattern"),
    (re.compile(r"\byes\s*\|"), "Infinite output pipe"),
    # Direct disk access
    (re.compile(r">\s*/dev/sd[a-z]"), "Direct disk write"),
    (re.compile(r">\s*/dev/nvme"), "Direct NVMe write"),
    (re.compile(r"\bdd\b.*of=/dev/"), "Direct disk write via dd"),
    (re.compile(r"\bmkfs\b"), "Filesystem creation/destruction"),
    # Privilege escalation
    (re.compile(r"\bsudo\b"), "Privilege escalation via sudo"),
    (re.compile(r"\bsu\s+-"), "Privilege escalation via su"),
    (re.compile(r"\bchmod\s+[0-7]*777\s+/"), "Dangerous permission change on root"),
    (re.compile(r"\bchown\s+-R\s+.*\s+/"), "Recursive ownership change on root"),
    # System modification
    (re.compile(r"\bsystemctl\s+(stop|disable|mask)"), "Service disruption"),
    (re.compile(r"\bkillall\b"), "Mass process termination"),
    (re.compile(r"\bpkill\s+-9"), "Forceful process termination"),
    # Network exfiltration (optional, can be disabled)
    (re.compile(r"\bnc\s+-l"), "Netcat listener (potential backdoor)"),
    (re.compile(r"\bssh\s+.*@"), "SSH connection"),
]


@dataclass
class SecurityPolicy:
    """
    Configurable security policy for command execution.

    Provides three security levels:
    - PERMISSIVE: Log dangerous commands but don't block
    - STANDARD: Block known-dangerous patterns (default)
    - PARANOID: Allowlist-only, deny everything not explicitly allowed
    """

    level: SecurityLevel = SecurityLevel.STANDARD
    blocked_patterns: list[tuple[re.Pattern[str], str]] = field(default_factory=list)
    allowed_commands: set[str] = field(default_factory=set)
    max_output_bytes: int = 30_000

    def __post_init__(self) -> None:
        """Initialize blocked patterns if using STANDARD level."""
        if self.level == SecurityLevel.STANDARD and not self.blocked_patterns:
            self.blocked_patterns = list(DANGEROUS_PATTERNS)

    @classmethod
    def permissive(cls) -> SecurityPolicy:
        """
        Create a permissive policy that logs but doesn't block.

        Use only in trusted environments for debugging.
        """
        return cls(level=SecurityLevel.PERMISSIVE)

    @classmethod
    def standard(cls) -> SecurityPolicy:
        """
        Create the standard security policy (recommended).

        Blocks known-dangerous command patterns.
        """
        return cls(
            level=SecurityLevel.STANDARD,
            blocked_patterns=list(DANGEROUS_PATTERNS),
        )

    @classmethod
    def paranoid(cls, allowed: set[str]) -> SecurityPolicy:
        """
        Create a paranoid policy that only allows specified commands.

        Args:
            allowed: Set of command names that are allowed (e.g., {"ls", "cat", "grep"}).
        """
        return cls(
            level=SecurityLevel.PARANOID,
            allowed_commands=allowed,
        )

    def check_command(self, command: str) -> str:
        """
        Validate command against the security policy.

        Args:
            command: The command string to validate.

        Returns:
            The (potentially modified) command to execute.

        Raises:
            SecurityViolation: If the command is blocked.
        """
        if self.level == SecurityLevel.PERMISSIVE:
            return command

        # Pattern blocking for STANDARD and PARANOID levels
        if self.level in (SecurityLevel.STANDARD, SecurityLevel.PARANOID):
            for pattern, reason in self.blocked_patterns:
                if pattern.search(command):
                    raise SecurityViolation(reason, command)

        # Allowlist enforcement for PARANOID level
        if self.level == SecurityLevel.PARANOID:
            # Extract the base command (first word, ignoring env vars)
            parts = command.strip().split()
            base_cmd = ""
            for part in parts:
                if "=" not in part:  # Skip env var assignments
                    base_cmd = part.split("/")[-1]  # Handle absolute paths
                    break

            if base_cmd and base_cmd not in self.allowed_commands:
                raise SecurityViolation(f"Command '{base_cmd}' not in allowlist", command)

        return command



    def add_blocked_pattern(self, pattern: str, reason: str) -> None:
        """
        Add a custom blocked pattern.

        Args:
            pattern: Regex pattern string.
            reason: Human-readable reason for blocking.
        """
        self.blocked_patterns.append((re.compile(pattern), reason))

    def add_allowed_command(self, command: str) -> None:
        """
        Add a command to the allowlist (for PARANOID mode).

        Args:
            command: Command name to allow (e.g., "ls").
        """
        self.allowed_commands.add(command)
