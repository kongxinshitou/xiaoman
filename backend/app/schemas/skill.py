from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SkillCreate(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    skill_type: str = "llm"
    config: str = "{}"
    trigger_keywords: str = "[]"
    is_active: bool = True
    priority: int = 100


class SkillUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    skill_type: Optional[str] = None
    config: Optional[str] = None
    trigger_keywords: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


class SkillRead(BaseModel):
    id: str
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    skill_type: str
    config: str
    trigger_keywords: str
    is_active: bool
    priority: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
