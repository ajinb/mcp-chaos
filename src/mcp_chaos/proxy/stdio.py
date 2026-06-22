"""stdio transport proxy: spawn the real MCP server as a subprocess and sit on
its newline-delimited JSON-RPC stream, applying faults via ProxyEngine.
"""

from __future__ import annotations

import asyncio
import json
import sys

from .common import ProxyEngine


async def _pump_client_to_server(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
                                 engine: ProxyEngine) -> None:
    while not reader.at_eof():
        line = await reader.readline()
        if not line:
            break
        try:
            msg = json.loads(line)
            msg = engine.on_request_message(msg)
            line = (json.dumps(msg) + "\n").encode()
        except (json.JSONDecodeError, ValueError):
            pass  # forward non-JSON / unparseable lines verbatim
        writer.write(line)
        await writer.drain()


async def _pump_server_to_client(reader: asyncio.StreamReader, out, engine: ProxyEngine) -> None:
    while not reader.at_eof():
        line = await reader.readline()
        if not line:
            break
        try:
            msg = json.loads(line)
            msg = engine.on_response_message(msg)
            line = (json.dumps(msg) + "\n").encode()
        except (json.JSONDecodeError, ValueError):
            pass
        out.write(line)
        out.flush()


async def run_stdio_proxy(server_cmd: list[str], plan, strict: bool = False) -> int:
    """Wrap `server_cmd`, proxying this process's stdin/stdout through it."""
    engine = ProxyEngine(plan, strict=strict)
    proc = await asyncio.create_subprocess_exec(
        *server_cmd, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
    )

    loop = asyncio.get_running_loop()
    client_reader = asyncio.StreamReader()
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(client_reader), sys.stdin)

    await asyncio.gather(
        _pump_client_to_server(client_reader, proc.stdin, engine),
        _pump_server_to_client(proc.stdout, sys.stdout.buffer, engine),
    )
    return await proc.wait()
