"""
Core types and data models.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class SecurityLevel(Enum):
    """Security level for the sandbox."""
    
    STRICT = auto()
    """Maximum isolation. No network, read-only FS except workspace."""
    
    BALANCED = auto()
    """Standard isolation. Allowlisted network, read-only FS except workspace."""
    
    PERMISSIVE = auto()
    """Minimal isolation. Full network, but still filesystem restrictions."""


@dataclass(frozen=True)
class CommandResult:
    """Result of a command execution."""
    
    stdout: str
    """Standard output."""
    
    stderr: str
    """Standard error output."""
    
    exit_code: int
    """Exit status code (0 = success)."""
    
    timed_out: bool = False
    """Whether availability deadline was exceeded."""

    @property
    def is_success(self) -> bool:
        """True if exit_code is 0 and not timed out."""
        return self.exit_code == 0 and not self.timed_out
