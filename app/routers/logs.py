from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import LearningLogCreate, LearningLogResponse, LearningLogUpdate
from app.services import log_service

router = APIRouter(prefix="/api/logs", tags=["learning logs"])


@router.post("", response_model=LearningLogResponse, status_code=status.HTTP_201_CREATED)
def create_learning_log(payload: LearningLogCreate, db: Session = Depends(get_db)):
    return log_service.create_log(db, payload)


@router.get("", response_model=list[LearningLogResponse])
def list_learning_logs(
    username: str = Query(default="default"),
    log_date: date | None = Query(default=None, alias="date"),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return log_service.list_logs(db, username=username, log_date=log_date, keyword=keyword)


@router.get("/{log_id}", response_model=LearningLogResponse)
def get_learning_log(
    log_id: int,
    username: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    log = log_service.get_log(db, log_id, username=username)
    if log is None:
        raise HTTPException(status_code=404, detail="学习日志不存在")
    return log


@router.patch("/{log_id}", response_model=LearningLogResponse)
def update_learning_log(
    log_id: int,
    payload: LearningLogUpdate,
    db: Session = Depends(get_db),
):
    log = log_service.update_log(db, log_id, payload)
    if log is None:
        raise HTTPException(status_code=404, detail="学习日志不存在")
    return log


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_learning_log(
    log_id: int,
    username: str = Query(default="default"),
    db: Session = Depends(get_db),
):
    deleted = log_service.delete_log(db, log_id, username=username)
    if not deleted:
        raise HTTPException(status_code=404, detail="学习日志不存在")
    return None
