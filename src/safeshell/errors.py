"""
Custom exceptions for consistent error handling.
"""

class SafeShellError(Exception):
    """Base class for all library exceptions."""
    pass


class ConfigurationError(SafeShellError):
    """Invalid configuration provided."""
    pass


class SecurityViolation(SafeShellError):
    """Operation blocked by security policy."""
    pass


class ExecutionError(SafeShellError):
    """Command execution failed (system error, not command error)."""
    pass


class DependencyError(SafeShellError):
    """Required external dependency (e.g. Docker) not found."""
    pass
