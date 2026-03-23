from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class MCPToolCreate(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    server_url: str
    transport: str = "sse"
    tool_schema: str = "{}"
    is_active: bool = True
    timeout_secs: int = 30


class MCPToolUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    server_url: Optional[str] = None
    transport: Optional[str] = None
    tool_schema: Optional[str] = None
    is_active: Optional[bool] = None
    timeout_secs: Optional[int] = None


class MCPToolRead(BaseModel):
    id: str
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    server_url: str
    transport: str
    tool_schema: str
    is_active: bool
    timeout_secs: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
