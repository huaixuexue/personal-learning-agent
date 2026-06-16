from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models import PlanItem
from app.schemas import PlanItemBulkSave
from app.services.log_service import normalize_username

VALID_STATUSES = {"pending", "done", "failed"}


def normalize_status(value: str | None) -> str:
    status = (value or "pending").strip()
    return status if status in VALID_STATUSES else "pending"


def list_plan_items(db: Session, username: str, target_date: date) -> list[PlanItem]:
    return (
        db.query(PlanItem)
        .filter(
            PlanItem.username == normalize_username(username),
            PlanItem.date == target_date,
        )
        .order_by(PlanItem.sort_order.asc(), PlanItem.id.asc())
        .all()
    )


def replace_plan_items(db: Session, payload: PlanItemBulkSave) -> list[PlanItem]:
    username = normalize_username(payload.username)
    existing = {
        item.id: item
        for item in list_plan_items(db, username, payload.date)
    }
    keep_ids: set[int] = set()

    for index, item in enumerate(payload.items):
        content = item.content.strip()
        if not content:
            continue
        if item.id and item.id in existing:
            row = existing[item.id]
            keep_ids.add(row.id)
            row.content = content
            row.status = normalize_status(item.status)
            row.sort_order = item.sort_order if item.sort_order is not None else index
        else:
            row = PlanItem(
                username=username,
                date=payload.date,
                content=content,
                status=normalize_status(item.status),
                sort_order=item.sort_order if item.sort_order is not None else index,
            )
            db.add(row)

    for row_id, row in existing.items():
        if row_id not in keep_ids:
            db.delete(row)

    db.commit()
    return list_plan_items(db, username, payload.date)


def set_status(db: Session, username: str, item_id: int, status: str) -> PlanItem | None:
    row = (
        db.query(PlanItem)
        .filter(PlanItem.id == item_id, PlanItem.username == normalize_username(username))
        .first()
    )
    if row is None:
        return None
    row.status = normalize_status(status)
    db.commit()
    db.refresh(row)
    return row


def apply_plan_text(db: Session, username: str, target_date: date | str, text: str) -> list[PlanItem]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        cleaned = line
        for prefix in ("- ", "* "):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        if ". " in cleaned and cleaned.split(". ", 1)[0].isdigit():
            cleaned = cleaned.split(". ", 1)[1].strip()
        if cleaned:
            lines.append(cleaned)

    payload = PlanItemBulkSave(
        username=username,
        date=target_date,
        items=[
            {"content": line, "status": "pending", "sort_order": index}
            for index, line in enumerate(lines)
        ],
    )
    return replace_plan_items(db, payload)
