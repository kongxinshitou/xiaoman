from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class FeishuConfigUpdate(BaseModel):
    app_id: Optional[str] = None
    app_secret: Optional[str] = None      # plain text, will be encrypted
    verify_token: Optional[str] = None
    encrypt_key: Optional[str] = None
    default_push_chat_id: Optional[str] = None
    enabled: Optional[bool] = None


class FeishuConfigRead(BaseModel):
    id: str
    app_id: str
    verify_token: str
    encrypt_key: str
    default_push_chat_id: str
    enabled: bool
    has_app_secret: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class FeishuPushRequest(BaseModel):
    title: str
    content: str
    chat_id: Optional[str] = None   # override default push target
