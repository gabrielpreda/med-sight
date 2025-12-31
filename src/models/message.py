"""Message models for conversation management"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class MessageRole(str, Enum):
    """Message role enumeration"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    """Conversation message model"""
    
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    images: Optional[List[str]] = None  # Base64 encoded images
    documents: Optional[List[str]] = None  # Document references
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class ConversationSession(BaseModel):
    """Conversation session model"""
    
    session_id: str
    user_id: Optional[str] = None
    messages: List[Message] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def add_message(self, message: Message):
        """Add a message to the session"""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()
    
    def get_recent_messages(self, n: int = 10) -> List[Message]:
        """Get the n most recent messages"""
        return self.messages[-n:]
    
    class Config:
        arbitrary_types_allowed = True
