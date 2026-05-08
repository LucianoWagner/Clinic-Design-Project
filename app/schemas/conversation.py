from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.models.enums import Channel


class ConversationCreate(BaseModel):
    channel: Channel = Channel.web_chat


class ConversationRead(BaseModel):
    id: int
    user_id: int
    channel: Channel
    status: str
    current_state: str
    title: str
    preview: str | None = None
    created_at: datetime
    updated_at: datetime
    last_messages: list["ConversationMessageRead"] = Field(default_factory=list)


class ConversationMessageRead(BaseModel):
    id: int
    conversation_id: int
    role: Literal["user", "assistant"]
    content: str
    input_mode: str
    created_at: datetime


class MessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    input_mode: Literal["text", "voice"] = "text"


class AgentAction(BaseModel):
    type: str
    payload: dict = Field(default_factory=dict)


class MessageRead(BaseModel):
    conversation_id: int
    response: str
    state: str
    actions: list[AgentAction] = Field(default_factory=list)
    transcript: Optional[str] = None
