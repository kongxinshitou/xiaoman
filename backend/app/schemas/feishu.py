from typing import Optional
from pydantic import BaseModel


class FeishuConfigUpdate(BaseModel):
    app_id: Optional[str] = None
    app_secret: Optional[str] = None       # plaintext, encrypted on write
    bot_open_id: Optional[str] = None
    default_push_chat_id: Optional[str] = None
    enabled: Optional[bool] = None


class FeishuConfigRead(BaseModel):
    app_id: Optional[str] = None
    has_app_secret: bool = False
    bot_open_id: Optional[str] = None
    default_push_chat_id: Optional[str] = None
    ws_connected: bool = False             # runtime status: is WS thread alive?
    enabled: bool = False

    model_config = {"from_attributes": True}


class FeishuPushRequest(BaseModel):
    chat_id: str
    message: str
    receive_id_type: str = "chat_id"


class FeishuCreateGroupRequest(BaseModel):
    name: str
    user_open_ids: list[str]
    description: str = ""
