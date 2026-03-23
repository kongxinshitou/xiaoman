from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class LLMProviderCreate(BaseModel):
    name: str
    provider_type: str
    base_url: Optional[str] = None
    api_key: str
    model_name: str
    is_active: bool = True
    is_default: bool = False


class LLMProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class LLMProviderRead(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: Optional[str] = None
    model_name: str
    is_active: bool
    is_default: bool
    last_test_status: str
    last_tested_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}
