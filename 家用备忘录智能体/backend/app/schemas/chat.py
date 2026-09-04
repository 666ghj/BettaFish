# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional, Any


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    intent: str
    reply: str
    data: Optional[Any] = None
    need_confirm: bool = False


class ChatHistory(BaseModel):
    id: str
    message: str
    reply: str
    created_at: str