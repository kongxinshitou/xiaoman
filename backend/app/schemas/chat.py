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


class ImageInfoSchema(BaseModel):
    id: str
    description: str = ""
    base64: Optional[str] = None


class MessageRead(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    meta: str = "{}"
    created_at: datetime
    # Inflated server-side from meta.images on history load so the frontend
    # can render [IMG_xxx] markers without refetching.
    images: Optional[List[ImageInfoSchema]] = None

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    session_id: str
    message: str
    provider_id: Optional[str] = None
    kb_ids: Optional[List[str]] = None
    stream: bool = True
    web_search: bool = False
    image_data_url: Optional[str] = None  # base64 data URL for vision input
