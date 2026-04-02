from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class SessionCreate(BaseModel):
    title: str = "新对话"
    active_provider_id: Optional[str] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    active_provider_id: Optional[str] = None


class SessionRead(BaseModel):
    id: str
    user_id: str
    title: str
    active_provider_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageRead(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    meta: str = "{}"
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    session_id: str
    message: str
    provider_id: Optional[str] = None
    kb_ids: Optional[List[str]] = None
    stream: bool = True
    web_search: bool = False
