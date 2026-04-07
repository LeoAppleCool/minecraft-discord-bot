import asyncio
import struct
import logging
from config import RCON_HOST, RCON_PORT, RCON_PASSWORD

log = logging.getLogger("rcon")

RCON_LOGIN    = 3
RCON_COMMAND  = 2
RCON_RESPONSE = 0


def _pack(req_id: int, req_type: int, payload: str) -> bytes:
    data = payload.encode("utf-8") + b"\x00\x00"
    header = struct.pack("<iii", len(data) + 8, req_id, req_type)
    return header + data


def _unpack(data: bytes):
    length = struct.unpack("<i", data[:4])[0]
    req_id, req_type = struct.unpack("<ii", data[4:12])
    payload = data[12:4 + length - 2].decode("utf-8", errors="replace")
    return req_id, req_type, payload


async def rcon_command(command: str) -> str:
    """Sends an RCON command and returns the server response."""
    reader, writer = await asyncio.open_connection(RCON_HOST, RCON_PORT)
    try:
        # Login
        writer.write(_pack(1, RCON_LOGIN, RCON_PASSWORD))
        await writer.drain()
        raw = await reader.read(4096)
        req_id, _, _ = _unpack(raw)
        if req_id == -1:
            raise ConnectionRefusedError("RCON: Wrong password")

        # Send command
        writer.write(_pack(2, RCON_COMMAND, command))
        await writer.drain()
        raw = await reader.read(4096)
        _, _, response = _unpack(raw)

        log.info(f"RCON << {command!r}  >>  {response!r}")
        return response
    finally:
        writer.close()
        await writer.wait_closed()
