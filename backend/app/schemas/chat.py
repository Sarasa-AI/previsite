from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List

class SessionCreate(BaseModel):
    initial_complaint: str

class SessionResponse(BaseModel):
    id: int
    patient_id: int
    patient_name: Optional[str] = None
    status: str
    initial_complaint: str
    created_at: datetime
    progress: int = 0
    
    model_config = ConfigDict(from_attributes=True)

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str  # "user" | "assistant"
    content: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ChatHistoryResponse(BaseModel):
    session: SessionResponse
    messages: List[MessageResponse]
