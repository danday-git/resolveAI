import socketserver
import struct
import threading

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import AuditEvent, Document

EICAR = rb"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


class FakeClamd(socketserver.StreamRequestHandler):
    """Speaks clamd's INSTREAM: flags any stream that holds the EICAR test string."""

    def handle(self):
        assert self.rfile.read(10) == b"zINSTREAM\0"
        body = b""
        while size := struct.unpack("!L", self.rfile.read(4))[0]:
            body += self.rfile.read(size)
        self.wfile.write(
            self.server.reply
            or (  # type: ignore[attr-defined]
                b"stream: Eicar-Test-Signature FOUND\0" if EICAR in body else b"stream: OK\0"
            )
        )


@pytest.fixture
def clamd(monkeypatch):
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FakeClamd)
    server.reply = None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(get_settings(), "clamav_host", "127.0.0.1")
    monkeypatch.setattr(get_settings(), "clamav_port", server.server_address[1])
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def upload(client, headers, name, data):
    files = {"file": (name, data, "text/plain")}
    return client.post("/api/v1/documents", headers=headers, files=files)


def test_clean_file_passes_and_infected_file_is_never_stored(client, auth_headers, clamd, db):
    clean = upload(client, auth_headers, "runbook.txt", b"Restart nginx when the upstream is down.")
    assert clean.status_code == 202

    infected = upload(client, auth_headers, "notes.txt", b"harmless looking notes\n" + EICAR)
    assert infected.status_code == 400
    assert infected.json()["error"]["code"] == "MALWARE_DETECTED"
    assert [d.filename for d in db.scalars(select(Document))] == ["runbook.txt"]
    event = db.scalar(select(AuditEvent).where(AuditEvent.action == "document.malware_rejected"))
    assert event.detail == {"signature": "Eicar-Test-Signature"}


def test_upload_is_refused_when_the_scanner_is_down_or_errors(client, auth_headers, clamd, db):
    clamd.reply = b"INSTREAM size limit exceeded. ERROR\0"
    assert upload(client, auth_headers, "a.txt", b"some operational text").status_code == 503
    clamd.shutdown()
    clamd.server_close()
    down = upload(client, auth_headers, "b.txt", b"some other operational text")
    assert down.status_code == 503
    assert down.json()["error"]["code"] == "SCANNER_UNAVAILABLE"
    assert db.scalars(select(Document)).all() == []
