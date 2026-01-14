"""
Native OS sandbox backend (Seatbelt/Landlock).
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
from enum import Enum, auto
from typing import Optional

from safeshell.core import BaseSandbox
from safeshell.errors import ExecutionError
from safeshell.networking import NetworkAllowlist, NetworkMode, AllowlistProxy
from safeshell.types import CommandResult
from safeshell.sandbox.seatbelt import SeatbeltProfile, build_sandboxed_command as build_seatbelt
from safeshell.sandbox.landlock import build_isolated_command as build_landlock


class KernelIsolation(Enum):
    """Available kernel isolation mechanisms."""
    NONE = auto()
    SEATBELT = auto()
    LANDLOCK = auto()


def _detect_kernel_isolation() -> KernelIsolation:
    """Detect available kernel isolation mechanism."""
    sys = platform.system()
    if sys == "Darwin":
        if shutil.which("sandbox-exec"):
            return KernelIsolation.SEATBELT
    elif sys == "Linux":
        # Simplified check for kernel 5.13+
        try:
            rel = platform.release().split(".")
            major, minor = int(rel[0]), int(rel[1].split("-")[0])
            if major > 5 or (major == 5 and minor >= 13):
                return KernelIsolation.LANDLOCK
        except Exception:
            pass
    return KernelIsolation.NONE


class NativeSandbox(BaseSandbox):
    """
    Executes commands using host OS kernel isolation.
    """

    def __init__(
        self, 
        cwd: str, 
        timeout: float = 30.0,
        network: NetworkMode = NetworkMode.BLOCKED,
        allowlist: Optional[NetworkAllowlist] = None
    ) -> None:
        super().__init__(cwd, timeout)
        self.network = network
        self.allowlist = allowlist
        
        self._mechanism = _detect_kernel_isolation()
        self._proxy: Optional[AllowlistProxy] = None
        self._proxy_port: int = 0

    async def execute(
        self, 
        command: str, 
        *, 
        timeout: Optional[float] = None
    ) -> CommandResult:
        if self._closed:
            raise ExecutionError("Sandbox is closed.")

        timeout_val = timeout if timeout is not None else self.timeout
        env = os.environ.copy()

        # Handle Proxy if needed
        if not self._proxy and self.network == NetworkMode.ALLOWLIST and self.allowlist:
            self._proxy = AllowlistProxy(self.allowlist)
            self._proxy_port = await self._proxy.start()

        if self._proxy_port:
            proxy_url = f"http://127.0.0.1:{self._proxy_port}"
            env.update({
                "HTTP_PROXY": proxy_url,
                "HTTPS_PROXY": proxy_url,
                "http_proxy": proxy_url,
                "https_proxy": proxy_url
            })

        # Build Command
        cmd_list = self._build_command(command)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_list,
                cwd=self.cwd,
                env=env,
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
            try: proc.kill()
            except: pass
            return CommandResult("", "Command timed out.", -1, timed_out=True)
            
        except Exception as e:
            raise ExecutionError(f"Native execution failed: {e}") from e

    def _build_command(self, command: str) -> list[str]:
        allow_net = self.network != NetworkMode.BLOCKED
        
        if self._mechanism == KernelIsolation.SEATBELT:
            profile = SeatbeltProfile(self.cwd, allow_network=allow_net)
            return build_seatbelt(command, profile)
            
        elif self._mechanism == KernelIsolation.LANDLOCK:
            return build_landlock(command, self.cwd, allow_network=allow_net)
            
        return ["bash", "-c", command]

    async def close(self) -> None:
        self._closed = True
        if self._proxy:
            await self._proxy.stop()
            self._proxy = None
