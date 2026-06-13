from datetime import date as DateType
from datetime import datetime

from pydantic import BaseModel, Field


class LearningLogBase(BaseModel):
    date: DateType
    content: str = Field(..., min_length=1, description="今日学习日志原文")
    tasks: str = Field(default="", description="今日完成的任务")
    problems: str = Field(default="", description="遇到的问题")
    tomorrow_plan: str = Field(default="", description="明日计划")
    category: str = Field(default="", description="任务类别")
    status: str = Field(default="进行中", description="完成状态")
    duration_minutes: int = Field(default=0, ge=0, description="学习耗时，单位分钟")
    remark: str = Field(default="", description="备注")


class LearningLogCreate(LearningLogBase):
    pass


class LearningLogUpdate(BaseModel):
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
