import socket
import struct

from app.core.config import get_settings
from app.core.errors import ApiError


def scan_upload(data: bytes) -> None:
    """Rejects a file ClamAV flags. Off unless CLAMAV_HOST is set; once set it fails closed:
    an upload that cannot be scanned is refused, never stored."""
    settings = get_settings()
    if not settings.clamav_host:
        return
    try:
        with socket.create_connection((settings.clamav_host, settings.clamav_port), 10) as clamd:
            clamd.settimeout(60)
            # clamd INSTREAM: length-prefixed chunks, ended by an empty one.
            clamd.sendall(
                b"zINSTREAM\0" + struct.pack("!L", len(data)) + data + struct.pack("!L", 0)
            )
            reply = b""
            while not reply.endswith(b"\0") and (part := clamd.recv(4096)):
                reply += part
    except OSError:
        raise ApiError(
            503, "SCANNER_UNAVAILABLE", "Uploads are paused: the malware scanner is unreachable"
        ) from None
    verdict = reply.rstrip(b"\0").decode(errors="replace").strip()
    if verdict.endswith("FOUND"):
        signature = verdict.removeprefix("stream:").removesuffix("FOUND").strip()
        raise ApiError(
            400,
            "MALWARE_DETECTED",
            "The malware scanner rejected this file",
            {"signature": signature},
        )
    if verdict != "stream: OK":
        raise ApiError(503, "SCANNER_UNAVAILABLE", "Uploads are paused: the malware scan failed")
