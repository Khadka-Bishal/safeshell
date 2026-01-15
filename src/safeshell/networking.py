"""
Proxy server implementation for network isolation.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from typing import TYPE_CHECKING

import h11

if TYPE_CHECKING:
    from asyncio import StreamReader, StreamWriter

    from safeshell.types import NetworkAllowlist

logger = logging.getLogger(__name__)


class AllowlistProxy:
    """
    An HTTP CONNECT proxy that enforces an allowlist.
    """

    def __init__(self, allowlist: NetworkAllowlist):
        self.allowlist = allowlist
        self._server: asyncio.AbstractServer | None = None
        self._port: int = 0

    async def start(self) -> int:
        """Start the proxy server and return the listening port."""
        self._server = await asyncio.start_server(
            self._handle_client,
            host="127.0.0.1",
            port=0,
            family=socket.AF_INET
        )

        sockets = self._server.sockets
        if not sockets:
            raise RuntimeError("Failed to start proxy server: no sockets allocated.")

        self._port = sockets[0].getsockname()[1]
        return self._port

    async def stop(self) -> None:
        """Stop the proxy server and wait for cleanup."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle_client(self, reader: StreamReader, writer: StreamWriter) -> None:
        """Handle an incoming client connection."""
        try:
            conn = h11.Connection(our_role=h11.SERVER)

            while True:
                data = await reader.read(4096)
                conn.receive_data(data)

                event = conn.next_event()
                if event is h11.NEED_DATA:
                    if not data:
                        break
                    continue

                elif isinstance(event, h11.Request):
                    await self._process_request(conn, event, reader, writer)
                    break

                elif isinstance(event, h11.ConnectionClosed):
                    return

                else:
                    await self._send_error(conn, writer, 400, "Bad Request")
                    return

        except Exception:
            pass  # Connection errors are expected in a proxy
        finally:
            with contextlib.suppress(Exception):
                writer.close()
                await writer.wait_closed()

    async def _process_request(
        self,
        conn: h11.Connection,
        request: h11.Request,
        reader: StreamReader,
        writer: StreamWriter
    ) -> None:
        method = request.method.decode()
        target = request.target.decode()

        # Only support CONNECT (HTTPS tunneling)
        if method == "CONNECT":
            try:
                host, port_str = target.split(":")
                port = int(port_str)
            except ValueError:
                await self._send_error(conn, writer, 400, "Invalid Target")
                return

            if self.allowlist.is_allowed(host, port):
                # Accept tunnel
                res = h11.Response(status_code=200, reason=b"Connection Established", headers=[])
                writer.write(conn.send(res))
                writer.write(conn.send(h11.EndOfMessage()))
                await writer.drain()

                # Switch to bi-directional tunneling
                await self._tunnel(reader, writer, host, port)
            else:
                await self._send_error(conn, writer, 403, "Forbidden by Sandbox")

        else:
             # Plain HTTP proxying is disabled for security and simplicity
             await self._send_error(conn, writer, 501, "Only CONNECT is supported")

    async def _send_error(self, conn: h11.Connection, writer: StreamWriter, code: int, msg: str) -> None:
        res = h11.Response(status_code=code, reason=msg.encode(), headers=[])
        writer.write(conn.send(res))
        writer.write(conn.send(h11.EndOfMessage()))
        await writer.drain()

    async def _tunnel(
        self,
        client_reader: StreamReader,
        client_writer: StreamWriter,
        remote_host: str,
        remote_port: int
    ) -> None:
        """Bidirectional data piping between client and remote."""
        try:
            remote_reader, remote_writer = await asyncio.open_connection(remote_host, remote_port)

            # Pipe data in both directions concurrently
            await asyncio.gather(
                self._pipe(client_reader, remote_writer),
                self._pipe(remote_reader, client_writer),
                return_exceptions=True
            )
        except Exception:
            pass

    async def _pipe(self, reader: StreamReader, writer: StreamWriter) -> None:
        """Transfer data from reader to writer until EOF."""
        try:
            while True:
                data = await reader.read(4096)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except Exception:
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()
