from pathlib import Path

from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import UploadedFileResponse
from app.services import file_service

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=UploadedFileResponse)
def upload_file(
    username: str = Query(..., min_length=1),
    upload_date: date | None = Query(default=None, alias="date"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return file_service.save_upload(db, username, file, target_date=upload_date)


@router.get("", response_model=list[UploadedFileResponse])
def list_uploaded_files(
    username: str = Query(..., min_length=1),
    scope: str = Query(default="history"),
    upload_date: date | None = Query(default=None, alias="date"),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return file_service.list_files(db, username, scope=scope, upload_date=upload_date, keyword=keyword)


@router.get("/{file_id}/view")
def view_file(
    file_id: int,
    username: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    row = file_service.get_file(db, username, file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Stored file missing")
    return FileResponse(
        path,
        media_type=row.file_type or "application/octet-stream",
        headers={"Content-Disposition": "inline"},
    )


@router.get("/{file_id}/download")
def download_file(
    file_id: int,
    username: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    row = file_service.get_file(db, username, file_id)
    if row is None:
        raise HTTPException(status_code=404, detail="File not found")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Stored file missing")
    return FileResponse(path, filename=row.original_name, media_type="application/octet-stream")


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: int,
    username: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    deleted = file_service.delete_file(db, username, file_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return None
