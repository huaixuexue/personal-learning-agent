from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import export_service

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/word")
def export_word(
    username: str = Query(..., min_length=1),
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
):
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="起始日期不能晚于终止日期")

    content = export_service.build_export_docx(db, username, start_date, end_date)
    filename = f"学习记录_{start_date}_{end_date}.docx"
    encoded = quote(filename)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}",
        },
    )
