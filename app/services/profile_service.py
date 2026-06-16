from sqlalchemy.orm import Session

from app.models import UserProfile
from app.schemas import UserProfileSave
from app.services.log_service import normalize_username


PROFILE_FIELDS = (
    "professional_identity",
    "research_direction",
    "goal_profile",
    "ability_status",
    "knowledge_mastery",
    "execution_habits",
    "time_constraints",
    "risk_preference",
    "memory_notes",
)


def empty_profile(username: str) -> dict[str, str | None]:
    data: dict[str, str | None] = {"id": None, "username": normalize_username(username)}
    for field in PROFILE_FIELDS:
        data[field] = ""
    data["created_at"] = None
    data["updated_at"] = None
    return data


def get_profile(db: Session, username: str) -> UserProfile | None:
    return (
        db.query(UserProfile)
        .filter(UserProfile.username == normalize_username(username))
        .first()
    )


def save_profile(db: Session, payload: UserProfileSave) -> UserProfile:
    username = normalize_username(payload.username)
    profile = get_profile(db, username)
    if profile is None:
        profile = UserProfile(username=username)
        db.add(profile)

    for field in PROFILE_FIELDS:
        setattr(profile, field, getattr(payload, field).strip())

    db.commit()
    db.refresh(profile)
    return profile


def format_profile_for_prompt(db: Session, username: str) -> str:
    profile = get_profile(db, username)
    if profile is None:
        return "用户暂未填写学习数字孪生画像。"

    rows = [
        ("专业身份", profile.professional_identity),
        ("研究方向", profile.research_direction),
        ("目标画像", profile.goal_profile),
        ("能力状态", profile.ability_status),
        ("知识掌握度", profile.knowledge_mastery),
        ("执行习惯", profile.execution_habits),
        ("时间约束", profile.time_constraints),
        ("风险偏好", profile.risk_preference),
        ("补充记忆", profile.memory_notes),
    ]
    content = "\n".join(f"{label}：{value}" for label, value in rows if value.strip())
    return content or "用户暂未填写学习数字孪生画像。"
