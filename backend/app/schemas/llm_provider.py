from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class LLMProviderCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str
    provider_type: str
    base_url: Optional[str] = None
    api_key: str
    model_name: str
    is_active: bool = True
    is_default: bool = False
    supports_vision: bool = False


class LLMProviderUpdate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None
    supports_vision: Optional[bool] = None


class LLMProviderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: str
    name: str
    provider_type: str
    base_url: Optional[str] = None
    model_name: str
    is_active: bool
    is_default: bool
    supports_vision: bool = False
    last_test_status: str
    last_tested_at: Optional[datetime] = None
    created_at: datetime


class FetchModelsRequest(BaseModel):
    provider_type: str
    api_key: str
    base_url: Optional[str] = None


class FetchModelsResponse(BaseModel):
    models: List[str]
