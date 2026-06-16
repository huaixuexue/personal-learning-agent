from __future__ import annotations

import re
import uuid
import zipfile
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models import UploadedFile
from app.services.log_service import normalize_username

UPLOAD_ROOT = Path("uploads")
TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".py", ".js", ".html", ".css"}


def safe_filename(name: str) -> str:
    clean = Path(name or "upload.bin").name
    return re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", clean)[:160] or "upload.bin"


def extract_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return extract_docx_text(path)
    if path.suffix.lower() == ".pdf":
        return extract_pdf_text(path)
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:12000]
    except OSError:
        return ""


def extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as docx:
            xml_bytes = docx.read("word/document.xml")
    except (KeyError, OSError, zipfile.BadZipFile):
        return ""

    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return ""

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        parts = [
            node.text or ""
            for node in paragraph.findall(".//w:t", namespace)
        ]
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)[:12000]


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages[:20]:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text.strip())
        return "\n\n".join(pages)[:12000]
    except Exception:
        return ""


def summarize_text(text: str, original_name: str) -> str:
    if not text.strip():
        return f"{original_name} uploaded. No readable text was extracted yet."
    compact = " ".join(text.split())
    return compact[:900]


def save_upload(
    db: Session,
    username: str,
    file: UploadFile,
    target_date: date | None = None,
) -> UploadedFile:
    user = normalize_username(username)
    today = target_date or date.today()
    original_name = safe_filename(file.filename or "upload.bin")
    stored_name = f"{uuid.uuid4().hex}_{original_name}"
    user_dir = UPLOAD_ROOT / user / today.isoformat()
    user_dir.mkdir(parents=True, exist_ok=True)
    target = user_dir / stored_name

    size = 0
    with target.open("wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            out.write(chunk)

    text = extract_text(target)
    row = UploadedFile(
        username=user,
        original_name=original_name,
        stored_name=stored_name,
        file_path=str(target),
        file_type=file.content_type or target.suffix.lower(),
        file_size=size,
        upload_date=today,
        extracted_text=text,
        summary=summarize_text(text, original_name),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_files(
    db: Session,
    username: str,
    scope: str = "history",
    upload_date: date | None = None,
    keyword: str | None = None,
) -> list[UploadedFile]:
    query = db.query(UploadedFile).filter(UploadedFile.username == normalize_username(username))
    if scope == "today":
        query = query.filter(UploadedFile.upload_date == date.today())
    elif upload_date is not None:
        query = query.filter(UploadedFile.upload_date == upload_date)
    if keyword and keyword.strip():
        query = query.filter(UploadedFile.original_name.like(f"%{keyword.strip()}%"))
    return query.order_by(UploadedFile.created_at.desc(), UploadedFile.id.desc()).all()


def get_file(db: Session, username: str, file_id: int) -> UploadedFile | None:
    return (
        db.query(UploadedFile)
        .filter(UploadedFile.id == file_id, UploadedFile.username == normalize_username(username))
        .first()
    )


def ensure_extracted_text(db: Session, row: UploadedFile) -> UploadedFile:
    if row.extracted_text:
        return row
    path = Path(row.file_path)
    if not path.exists():
        return row
    text = extract_text(path)
    if text:
        row.extracted_text = text
        row.summary = summarize_text(text, row.original_name)
        db.commit()
        db.refresh(row)
    return row


def delete_file(db: Session, username: str, file_id: int) -> bool:
    row = get_file(db, username, file_id)
    if row is None:
        return False
    path = Path(row.file_path)
    if path.exists() and path.is_file():
        path.unlink()
    db.delete(row)
    db.commit()
    return True


def format_files_for_prompt(files: list[UploadedFile]) -> str:
    if not files:
        return ""
    chunks = []
    for item in files:
        text = item.extracted_text or item.summary
        chunks.append(
            "\n".join(
                [
                    f"File: {item.original_name}",
                    f"Uploaded: {item.upload_date}",
                    f"Summary: {item.summary}",
                    f"Content excerpt: {text[:3000]}",
                ]
            )
        )
    return "\n\n---\n\n".join(chunks)
