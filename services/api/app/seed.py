import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.core.security_text import redact
from app.models import Document, DocumentStatus, Incident, IncidentSeverity, User
from app.services.ingestion.pipeline import ingest_document


def seed(fixtures_dir: Path | None = None) -> None:
    settings = get_settings()
    if not settings.demo_user_password:
        raise RuntimeError("DEMO_USER_PASSWORD must be set to seed the demo user")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == settings.demo_user_email.lower()))
        if user is None:
            user = User(
                email=settings.demo_user_email.lower(),
                password_hash=hash_password(settings.demo_user_password),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        if fixtures_dir is None:
            fixtures_dir = Path(__file__).resolve().parents[3] / "evals" / "fixtures" / "docs"
        incident_path = fixtures_dir.parent / "incidents" / "nginx-502.json"
        if incident_path.exists():
            data = json.loads(incident_path.read_text())
            exists = db.scalar(
                select(Incident).where(
                    Incident.owner_id == user.id, Incident.title == data["title"]
                )
            )
            if exists is None:
                log = data.get("log_excerpt")
                sanitized, summary = redact(log or "")
                db.add(
                    Incident(
                        owner_id=user.id,
                        title=data["title"],
                        severity=IncidentSeverity(data.get("severity", "SEV2")),
                        service=data.get("service", "unknown"),
                        symptoms=data.get("symptoms", ""),
                        environment=data.get("environment"),
                        started_at=datetime.fromisoformat(data["started_at"])
                        if data.get("started_at")
                        else None,
                        detected_at=datetime.fromisoformat(data["detected_at"])
                        if data.get("detected_at")
                        else None,
                        sanitized_log=sanitized if log is not None else None,
                        redaction_summary=summary,
                    )
                )
                db.commit()
        if fixtures_dir.is_dir():
            for fixture in sorted(fixtures_dir.iterdir()):
                extension = fixture.suffix.lower()
                if not fixture.is_file() or extension not in {".pdf", ".txt", ".md"}:
                    continue
                contents = fixture.read_bytes()
                checksum = hashlib.sha256(contents).hexdigest()
                if db.scalar(
                    select(Document.id).where(
                        Document.owner_id == user.id, Document.sha256 == checksum
                    )
                ):
                    continue
                filename = re.sub(r"[^A-Za-z0-9._-]", "", fixture.name)[:120]
                document_id = uuid4()
                owner_dir = Path(settings.upload_dir) / str(user.id)
                owner_dir.mkdir(parents=True, exist_ok=True)
                path = owner_dir / f"{document_id}{extension}"
                path.write_bytes(contents)
                db.add(
                    Document(
                        id=document_id,
                        owner_id=user.id,
                        filename=filename,
                        mime_type={
                            ".pdf": "application/pdf",
                            ".txt": "text/plain",
                            ".md": "text/markdown",
                        }[extension],
                        sha256=checksum,
                        size_bytes=len(contents),
                        storage_path=str(path),
                        status=DocumentStatus.QUEUED,
                    )
                )
                db.commit()
                ingest_document(document_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-fixtures", action="store_true")
    parser.add_argument("--fixtures-dir", type=Path)
    args = parser.parse_args()
    seed(args.fixtures_dir if args.with_fixtures else None)


if __name__ == "__main__":
    main()
