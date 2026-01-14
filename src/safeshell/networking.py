"""
Networking types and logic (Proxy, AllocLists).
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Set

from safeshell.errors import ConfigurationError

logger = logging.getLogger(__name__)


class NetworkMode(Enum):
    """Network access control mode."""
    
    BLOCKED = "blocked"
    """No network access allowed."""
    
    ALLOWED = "allowed"
    """Full network access allowed."""
    
    ALLOWLIST = "allowlist"
    """Only specific domains allowed (requires allowlist)."""


@dataclass
class NetworkAllowlist:
    """Domain allowlist configuration."""
    
    domains: Set[str] = field(default_factory=set)

    def add(self, *domains: str) -> NetworkAllowlist:
        """Add domains to the allowlist."""
        for d in domains:
            self.domains.add(d.lower())
        return self

    def matches(self, domain: str) -> bool:
        """Check if domain is allowed (supports *.example.com wildcards)."""
        domain = domain.lower()
        for pattern in self.domains:
            if pattern.startswith("*."):
                suffix = pattern[1:]
                if domain.endswith(suffix) or domain == pattern[2:]:
                    return True
            elif domain == pattern:
                return True
        return False

    @classmethod
    def development(cls) -> NetworkAllowlist:
        """Standard development domains (pypi, npm, git, etc)."""
        return cls({
            "pypi.org", "*.pypi.org", "files.pythonhosted.org",
            "registry.npmjs.org", "*.npmjs.org",
            "github.com", "*.github.com", "gitlab.com", "*.gitlab.com",
            # CDNs
            "*.cloudflare.com", "*.fastly.net", "*.jsdelivr.net"
        })

    @classmethod
    def ai_apis(cls) -> NetworkAllowlist:
        """Major AI provider APIs."""
        return cls({
            "api.openai.com", "*.openai.com", 
            "api.anthropic.com", "generativelanguage.googleapis.com"
        })

    def __or__(self, other: NetworkAllowlist) -> NetworkAllowlist:
        return NetworkAllowlist(self.domains | other.domains)


class AllowlistProxy:
    """Simple HTTP CONNECT/Request filtering proxy."""

    def __init__(self, allowlist: NetworkAllowlist) -> None:
        self.allowlist = allowlist
        self._server: asyncio.Server | None = None
        self.port: int = 0

    async def start(self) -> int:
        """Start the proxy server on an ephemeral port."""
        self._server = await asyncio.start_server(
            self._handle_client, 
            host="127.0.0.1", 
            port=0
        )
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        """Stop the proxy server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle incoming proxy connection (HTTP/HTTPS)."""
        try:
            # Read first line: method target proto
            line = await asyncio.wait_for(reader.readline(), timeout=10.0)
            if not line: return
            
            req = line.decode(errors="replace").strip()
            parts = req.split()
            if len(parts) < 2: return

            method, target = parts[0], parts[1]
            domain = self._extract_domain(method, target)

            if not domain or not self.allowlist.matches(domain):
                logger.warning(f"Blocking {domain}")
                await self._send_error(writer, 403, f"Access to {domain} blocked by policy.")
                return

            logger.debug(f"Allowing {domain}")
            if method == "CONNECT":
                await self._tunnel_https(reader, writer, target)
            else:
                await self._proxy_http(reader, writer, req, domain)

        except Exception:
            pass  # Connection errors happen, don't crash proxy
        finally:
            writer.close()

    def _extract_domain(self, method: str, target: str) -> str | None:
        if method == "CONNECT": return target.split(":")[0]
        # GET http://example.com/foo
        match = re.match(r"(?:https?://)?([^/:]+)", target)
        return match.group(1) if match else None

    async def _tunnel_https(self, client_r, client_w, target: str):
        host, port = (target.split(":", 1) + ["443"])[:2]
        try:
            remote_r, remote_w = await asyncio.open_connection(host, int(port))
            client_w.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_w.drain()
            await self._pipe(client_r, client_w, remote_r, remote_w)
        except Exception:
            pass

    async def _proxy_http(self, client_r, client_w, req_line: str, host: str):
        try:
            # Minimal HTTP proxying (just forward)
            remote_r, remote_w = await asyncio.open_connection(host, 80)
            remote_w.write(f"{req_line}\r\n".encode())
            # Forward headers (simplified)
            while True:
                line = await client_r.readline()
                if not line or line == b"\r\n": break
                remote_w.write(line)
            remote_w.write(b"\r\n")
            await remote_w.drain()
            
            # Pipe response back
            # In a real senior-eng implementation, we'd use 'httpx' or 'aiohttp' 
            # but this raw socket code has 0 dependencies, which is better for this library.
            # However, simplified piping is tricky for HTTP due to keep-alive.
            # We'll do a simple one-shot read/write for now.
            data = await remote_r.read(65536)
            client_w.write(data)
            remote_w.close()
        except Exception:
            pass

    async def _pipe(self, cr, cw, rr, rw):
        async def cp(src, dst):
            while True:
                d = await src.read(8192)
                if not d: break
                dst.write(d)
                await dst.drain()
        await asyncio.gather(cp(cr, rw), cp(rr, cw), return_exceptions=True)

    async def _send_error(self, w, code, msg):
        w.write(f"HTTP/1.1 {code} Error\r\nConnection: close\r\n\r\n{msg}".encode())
        await w.drain()
