from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AIMessage
from app.schemas import AIApplyPlanRequest, AIChatRequest, AIChatResponse, AIMessageResponse
from app.services import ai_service, log_service, plan_service

router = APIRouter(prefix="/api/ai", tags=["ai assistant"])


@router.get("/messages", response_model=list[AIMessageResponse])
def list_ai_messages(
    username: str = Query(default=""),
    db: Session = Depends(get_db),
):
    if not username.strip():
        return []
    return (
        db.query(AIMessage)
        .filter(AIMessage.username == log_service.normalize_username(username))
        .order_by(AIMessage.id.asc())
        .all()
    )


@router.post("/chat", response_model=AIChatResponse)
def chat(payload: AIChatRequest, db: Session = Depends(get_db)):
    try:
        message = ai_service.chat(
            db,
            payload.username,
            payload.message.strip(),
            payload.selected_date,
            payload.file_ids,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"message": message}


@router.post("/apply-plan")
def apply_plan(payload: AIApplyPlanRequest, db: Session = Depends(get_db)):
    username = log_service.normalize_username(payload.username)
    message = (
        db.query(AIMessage)
        .filter(AIMessage.id == payload.message_id, AIMessage.username == username)
        .first()
    )
    if message is None or not message.plan_text:
        raise HTTPException(status_code=404, detail="没有可应用的计划")

    target_date = message.plan_date
    old = log_service.latest_by_date(db, target_date, username=username)
    log_service.create_snapshot(
        db,
        target_date,
        username=username,
        content=(old.content if old else "心情：开心 · 小心心\n\n"),
        tasks=message.plan_text,
        problems=(old.problems if old else ""),
        tomorrow_plan=(old.tomorrow_plan if old else ""),
        category=(old.category if old else "学习日志"),
        status=(old.status if old else "进行中"),
        duration_minutes=(old.duration_minutes if old else 0),
        remark=(old.remark if old else ""),
    )
    message.applied = 1
    plan_service.apply_plan_text(db, username, target_date, message.plan_text)
    db.commit()
    return {"date": target_date}
