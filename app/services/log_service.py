from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import LearningLog
from app.schemas import LearningLogCreate, LearningLogUpdate


def normalize_username(username: str | None) -> str:
    value = (username or "default").strip()
    return value or "default"


def create_log(db: Session, payload: LearningLogCreate) -> LearningLog:
    data = payload.model_dump()
    data["username"] = normalize_username(data.get("username"))
    log = LearningLog(**data)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def create_snapshot(
    db: Session,
    log_date: date | str,
    username: str = "default",
    content: str = "",
    tasks: str = "",
    problems: str = "",
    tomorrow_plan: str = "",
    category: str = "学习日志",
    status: str = "进行中",
    duration_minutes: int = 0,
    remark: str = "",
) -> LearningLog:
    payload = LearningLogCreate(
        username=normalize_username(username),
        date=log_date,
        content=content,
        tasks=tasks,
        problems=problems,
        tomorrow_plan=tomorrow_plan,
        category=category,
        status=status,
        duration_minutes=duration_minutes,
        remark=remark,
    )
    return create_log(db, payload)


def latest_by_date(db: Session, log_date: date | str, username: str = "default") -> LearningLog | None:
    return (
        db.query(LearningLog)
        .filter(LearningLog.username == normalize_username(username), LearningLog.date == log_date)
        .order_by(LearningLog.id.desc())
        .first()
    )


def list_logs(
    db: Session,
    username: str = "default",
    log_date: date | None = None,
    keyword: str | None = None,
) -> list[LearningLog]:
    query = db.query(LearningLog).filter(LearningLog.username == normalize_username(username))

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


def get_log(db: Session, log_id: int, username: str = "default") -> LearningLog | None:
    return (
        db.query(LearningLog)
        .filter(LearningLog.id == log_id, LearningLog.username == normalize_username(username))
        .first()
    )


def update_log(
    db: Session,
    log_id: int,
    payload: LearningLogUpdate,
) -> LearningLog | None:
    username = normalize_username(payload.username)
    log = get_log(db, log_id, username=username)
    if log is None:
        return None

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(log, field, normalize_username(value) if field == "username" else value)

    db.commit()
    db.refresh(log)
    return log


def delete_log(db: Session, log_id: int, username: str = "default") -> bool:
    log = get_log(db, log_id, username=username)
    if log is None:
        return False

    db.delete(log)
    db.commit()
    return True
