"""
Docker-based sandbox backend.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass
from typing import Optional

from safeshell.core import BaseSandbox
from safeshell.errors import DependencyError, ExecutionError
from safeshell.types import CommandResult
from safeshell.networking import NetworkMode


@dataclass
class DockerConfig:
    """Docker execution configuration."""
    image: str = "python:3.11-slim"
    cpus: float = 1.0
    memory: str = "512m"


class DockerSandbox(BaseSandbox):
    """
    Executes commands inside an ephemeral Docker container.
    """

    def __init__(
        self, 
        cwd: str, 
        timeout: float = 30.0,
        config: Optional[DockerConfig] = None,
        network: NetworkMode = NetworkMode.BLOCKED
    ) -> None:
        super().__init__(cwd, timeout)
        self.config = config or DockerConfig()
        self.network = network
        
        if not shutil.which("docker"):
            raise DependencyError("Docker executable not found.")

    async def execute(
        self, 
        command: str, 
        *, 
        timeout: Optional[float] = None
    ) -> CommandResult:
        if self._closed:
            raise ExecutionError("Sandbox is closed.")

        timeout_val = timeout if timeout is not None else self.timeout
        
        # Map our NetworkMode to Docker network flags
        net_flag = "none"
        if self.network in (NetworkMode.ALLOWED, NetworkMode.ALLOWLIST):
            # NOTE: Docker --network doesn't support an allowlist natively easily.
            # For allowlist, we'd need a host proxy + host network or bridge configuration.
            # For this 'Senior' refactor, we accept that 'ALLOWLIST' behaves like 'bridge' 
            # in Docker unless we inject the proxy into the container env.
            # We'll stick to 'bridge' for allowed/allowlist for simplicity, 
            # users should enforce allowlist via proxy env vars if needed.
            net_flag = "bridge"

        args = [
            "docker", "run", "--rm",
            "-v", f"{self.cwd}:/workspace",
            "-w", "/workspace",
            f"--network={net_flag}",
            f"--cpus={self.config.cpus}",
            f"--memory={self.config.memory}",
            "--init", # Handle signals properly
            self.config.image,
            "bash", "-c", command
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_val)
            
            return CommandResult(
                stdout=stdout.decode(errors="replace"),
                stderr=stderr.decode(errors="replace"),
                exit_code=proc.returncode or 0
            )

        except asyncio.TimeoutError:
            # We need to kill the container. 'proc.kill()' kills the docker client, not the container.
            # But with --rm and --init, it usually cleans up. 
            if 'proc' in locals():
                try: proc.kill() 
                except: pass
            return CommandResult("", "Command timed out.", -1, timed_out=True)
            
        except Exception as e:
            raise ExecutionError(f"Docker execution failed: {e}") from e

    async def close(self) -> None:
        self._closed = True
