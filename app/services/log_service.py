from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import LearningLog
from app.schemas import LearningLogCreate, LearningLogUpdate


def create_log(db: Session, payload: LearningLogCreate) -> LearningLog:
    log = LearningLog(**payload.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_logs(
    db: Session,
    log_date: date | None = None,
    keyword: str | None = None,
) -> list[LearningLog]:
    query = db.query(LearningLog)

    if log_date is not None:
        query = query.filter(LearningLog.date == log_date)

    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                LearningLog.content.like(pattern),
                LearningLog.tasks.like(pattern),
                LearningLog.problems.like(pattern),
                LearningLog.tomorrow_plan.like(pattern),
                LearningLog.category.like(pattern),
                LearningLog.remark.like(pattern),
            )
        )

    return query.order_by(LearningLog.date.desc(), LearningLog.id.desc()).all()


def get_log(db: Session, log_id: int) -> LearningLog | None:
    return db.query(LearningLog).filter(LearningLog.id == log_id).first()


def update_log(
    db: Session,
    log_id: int,
    payload: LearningLogUpdate,
) -> LearningLog | None:
    log = get_log(db, log_id)
    if log is None:
        return None

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(log, field, value)

    db.commit()
    db.refresh(log)
    return log


def delete_log(db: Session, log_id: int) -> bool:
    log = get_log(db, log_id)
    if log is None:
        return False

    db.delete(log)
    db.commit()
    return True
