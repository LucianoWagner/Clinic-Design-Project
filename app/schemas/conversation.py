from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.models.enums import Channel


class ConversationCreate(BaseModel):
    channel: Channel = Channel.web_chat


class ConversationRead(BaseModel):
    id: int
    channel: Channel
    status: str
    current_state: str


class MessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    input_mode: Literal["text", "voice"] = "text"


class AgentAction(BaseModel):
    type: str
    payload: dict = {}


class MessageRead(BaseModel):
    conversation_id: int
    response: str
    state: str
    actions: list[AgentAction] = []
    transcript: Optional[str] = None
