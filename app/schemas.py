
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ToolExecution(BaseModel):
    tool: str
    arguments: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    conversation_id: str
    response: str
    agent_mode: str
    escalated: bool = False
    ticket_id: str | None = None
    tool_calls: list[ToolExecution] = Field(default_factory=list)
