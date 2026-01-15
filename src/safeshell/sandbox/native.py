"""
Native OS sandbox backend (Seatbelt/Landlock).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import platform
import shutil
from enum import Enum, auto
from subprocess import PIPE

import psutil  # type: ignore

from safeshell.core import BaseSandbox
from safeshell.errors import ExecutionError
from safeshell.networking import AllowlistProxy
from safeshell.sandbox.landlock import build_isolated_command as build_landlock
from safeshell.sandbox.landlock import supports_namespaces
from safeshell.sandbox.seatbelt import SeatbeltProfile
from safeshell.sandbox.seatbelt import build_sandboxed_command as build_seatbelt
from safeshell.types import CommandResult, NetworkAllowlist, NetworkMode

logger = logging.getLogger(__name__)


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
        # We rely on 'unshare' for isolation.
        if supports_namespaces():
            return KernelIsolation.LANDLOCK
        else:
            logger.warning("Linux namespaces (unshare) not supported in this environment. sandbox will be disabled.")
    return KernelIsolation.NONE


class NativeSandbox(BaseSandbox):
    """
    Production-grade sandbox using OS-native isolation.
    """

    def __init__(
        self,
        cwd: str,
        timeout: float = 30.0,
        network: NetworkMode = NetworkMode.BLOCKED,
        allowlist: NetworkAllowlist | None = None,
    ):
        super().__init__(cwd=cwd, timeout=timeout)
        self.network = network
        self.allowlist = allowlist
        self._mechanism = _detect_kernel_isolation()
        self._proxy: AllowlistProxy | None = None
        self._proxy_port: int = 0

    def _kill_process_tree(self, pid: int) -> None:
        """Kill process and its children using psutil (synchronous)."""
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)

            # Kill children first
            for child in children:
                with contextlib.suppress(psutil.NoSuchProcess):
                    child.terminate()

            # Kill parent
            parent.terminate()

            # Ensure death
            _, alive = psutil.wait_procs([parent, *children], timeout=3)
            for p in alive:
                with contextlib.suppress(psutil.NoSuchProcess):
                    p.kill()
        except psutil.NoSuchProcess:
            pass
        except Exception:
            pass

    async def execute(
        self,
        command: str,
        *,
        timeout: float | None = None
    ) -> CommandResult:
        if self._closed:
            raise ExecutionError("Sandbox is closed.")

        timeout_val = timeout if timeout is not None else self.timeout
        env = os.environ.copy()

        # Build Command
        cmd_list = self._build_command(command)

        # Start Proxy if needed
        local_proxy = None
        if self.network == NetworkMode.ALLOWLIST and self.allowlist:
            local_proxy = AllowlistProxy(self.allowlist)
            self._proxy = local_proxy

            try:
                self._proxy_port = await local_proxy.start()
                proxy_url = f"http://127.0.0.1:{self._proxy_port}"
                env.update({
                    "HTTP_PROXY": proxy_url,
                    "HTTPS_PROXY": proxy_url,
                    "http_proxy": proxy_url,
                    "https_proxy": proxy_url
                })
            except Exception as e:
                raise ExecutionError(f"Failed to start proxy: {e}") from e

        try:
            # Execute Process
            proc = await asyncio.create_subprocess_exec(
                *cmd_list,
                cwd=self.cwd,
                env=env,
                stdout=PIPE,
                stderr=PIPE,
            )

            try:
                async with asyncio.timeout(timeout_val):
                    stdout, stderr = await proc.communicate()

                return CommandResult(
                    stdout=stdout.decode(errors="replace"),
                    stderr=stderr.decode(errors="replace"),
                    exit_code=proc.returncode or 0
                )

            except TimeoutError:
                if proc.pid:
                    self._kill_process_tree(proc.pid)

                with contextlib.suppress(Exception):
                    await proc.wait()

                return CommandResult(
                    stdout="",
                    stderr="Command timed out.",
                    exit_code=-1,
                    timed_out=True
                )

        except Exception as e:
            raise ExecutionError(f"Native execution failed: {e}") from e

        finally:
            if local_proxy:
                await local_proxy.stop()
                if self._proxy == local_proxy:
                    self._proxy = None

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
