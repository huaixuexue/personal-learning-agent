from datetime import date as DateType
from datetime import datetime

from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=128)


class AuthResponse(BaseModel):
    username: str
    created: bool = False


class LearningLogBase(BaseModel):
    username: str = Field(default="default", description="登录用户名")
    date: DateType
    content: str = Field(..., min_length=1, description="今日学习日志原文")
    tasks: str = Field(default="", description="今日计划")
    problems: str = Field(default="", description="待解决事项")
    tomorrow_plan: str = Field(default="", description="明日计划")
    category: str = Field(default="", description="任务类别")
    status: str = Field(default="进行中", description="完成状态")
    duration_minutes: int = Field(default=0, ge=0, description="学习耗时，单位分钟")
    remark: str = Field(default="", description="备注")


class LearningLogCreate(LearningLogBase):
    pass


class LearningLogUpdate(BaseModel):
    username: str | None = None
    date: DateType | None = None
    content: str | None = Field(default=None, min_length=1)
    tasks: str | None = None
    problems: str | None = None
    tomorrow_plan: str | None = None
    category: str | None = None
    status: str | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    remark: str | None = None


class LearningLogResponse(LearningLogBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIMessageResponse(BaseModel):
    id: int
    username: str = "default"
    role: str
    content: str
    plan_date: str = ""
    plan_text: str = ""
    applied: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class AIChatRequest(BaseModel):
    username: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    selected_date: DateType | None = None
    file_ids: list[int] = Field(default_factory=list)


class AIChatResponse(BaseModel):
    message: AIMessageResponse


class AIApplyPlanRequest(BaseModel):
    username: str = Field(..., min_length=1)
    message_id: int


class UserProfileBase(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    professional_identity: str = ""
    research_direction: str = ""
    goal_profile: str = ""
    ability_status: str = ""
    knowledge_mastery: str = ""
    execution_habits: str = ""
    time_constraints: str = ""
    risk_preference: str = ""
    memory_notes: str = ""


class UserProfileSave(UserProfileBase):
    pass


class UserProfileResponse(UserProfileBase):
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class UploadedFileResponse(BaseModel):
    id: int
    username: str
    original_name: str
    file_type: str = ""
    file_size: int = 0
    upload_date: DateType
    summary: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


class PlanItemBase(BaseModel):
    content: str = Field(..., min_length=1)
    status: str = Field(default="pending")
    sort_order: int = 0


class PlanItemSave(PlanItemBase):
    id: int | None = None


class PlanItemBulkSave(BaseModel):
    username: str = Field(..., min_length=1)
    date: DateType
    items: list[PlanItemSave] = Field(default_factory=list)


class PlanItemStatusUpdate(BaseModel):
    username: str = Field(..., min_length=1)
    status: str = Field(..., pattern="^(pending|done|failed)$")


class PlanItemResponse(PlanItemBase):
    id: int
    username: str
    date: DateType
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
