from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import UserProfileResponse, UserProfileSave
from app.services import profile_service

router = APIRouter(prefix="/api/profile", tags=["user profile"])


@router.get("", response_model=UserProfileResponse)
def get_profile(username: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    profile = profile_service.get_profile(db, username)
    if profile is None:
        return profile_service.empty_profile(username)
    return profile


@router.post("", response_model=UserProfileResponse)
def save_profile(payload: UserProfileSave, db: Session = Depends(get_db)):
    return profile_service.save_profile(db, payload)
