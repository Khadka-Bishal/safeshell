"""
Core types and data models for safeshell.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CommandResult(BaseModel):
    """Result of a command execution."""

    stdout: str = Field(description="Standard output.")
    stderr: str = Field(description="Standard error output.")
    exit_code: int = Field(description="Exit status code (0 = success).")
    timed_out: bool = Field(default=False, description="Whether execution deadline was exceeded.")

    @property
    def is_success(self) -> bool:
        """True if exit_code is 0 and execution did not time out."""
        return self.exit_code == 0 and not self.timed_out


class NetworkMode(str, Enum):
    """Network isolation configuration modes."""

    BLOCKED = "blocked"
    """Block all network access."""

    ALLOWLIST = "allowlist"
    """Allow access only to specific domains."""


class NetworkAllowlist(BaseModel):
    """Configuration for allowlisted network domains and ports."""

    domains: set[str] = Field(default_factory=set, description="Set of allowed domains (e.g. 'pypi.org').")
    allow_ports: set[int] = Field(default_factory=lambda: {80, 443}, description="Set of allowed TCP ports.")

    def is_allowed(self, host: str, port: int) -> bool:
        """
        Check if the given host and port are allowed.
        Matches exact domains or subdomains (e.g., 'pypi.org' matches 'files.pypi.org').
        """
        if port not in self.allow_ports:
            return False

        # Check for exact match or subdomain match
        return any(
            host == domain or host.endswith(f".{domain}")
            for domain in self.domains
        )

    @classmethod
    def development(cls) -> NetworkAllowlist:
        """
        Create a configuration allowing standard development domains.
        Includes PyPI, GitHub, npm, and Yarn.
        """
        return cls(domains={
            "pypi.org",
            "files.pythonhosted.org",
            "github.com",
            "npmjs.org",
            "yarnpkg.com",
        })
