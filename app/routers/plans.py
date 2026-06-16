from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import PlanItemBulkSave, PlanItemResponse, PlanItemStatusUpdate
from app.services import plan_service

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("", response_model=list[PlanItemResponse])
def list_plan_items(
    username: str = Query(..., min_length=1),
    plan_date: date = Query(..., alias="date"),
    db: Session = Depends(get_db),
):
    return plan_service.list_plan_items(db, username, plan_date)


@router.post("/bulk", response_model=list[PlanItemResponse])
def save_plan_items(payload: PlanItemBulkSave, db: Session = Depends(get_db)):
    return plan_service.replace_plan_items(db, payload)


@router.patch("/{item_id}/status", response_model=PlanItemResponse)
def update_plan_status(
    item_id: int,
    payload: PlanItemStatusUpdate,
    db: Session = Depends(get_db),
):
    row = plan_service.set_status(db, payload.username, item_id, payload.status)
    if row is None:
        raise HTTPException(status_code=404, detail="Plan item not found")
    return row
