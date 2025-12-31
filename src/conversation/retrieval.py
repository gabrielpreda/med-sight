"""Retrieval utilities for conversation context"""

from typing import List, Dict, Optional
import logging
from datetime import datetime, timedelta

from ..models.message import ConversationSession, Message


class ConversationRetrieval:
    """Retrieves relevant conversation context"""
    
    def __init__(self):
        """Initialize conversation retrieval"""
        self.logger = logging.getLogger(__name__)
    
    def get_messages_by_timeframe(
        self,
        session: ConversationSession,
        hours: int = 24
    ) -> List[Message]:
        """
        Get messages within a timeframe.
        
        Args:
            session: Conversation session
            hours: Number of hours to look back
        
        Returns:
            List of messages
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return [
            msg for msg in session.messages
            if msg.timestamp >= cutoff_time
        ]
    
    def get_messages_with_images(self, session: ConversationSession) -> List[Message]:
        """Get all messages that contain images"""
        return [msg for msg in session.messages if msg.images]
    
    def get_messages_with_documents(self, session: ConversationSession) -> List[Message]:
        """Get all messages that contain documents"""
        return [msg for msg in session.messages if msg.documents]
    
    def search_messages(
        self,
        session: ConversationSession,
        query: str,
        case_sensitive: bool = False
    ) -> List[Message]:
        """
        Search messages by content.
        
        Args:
            session: Conversation session
            query: Search query
            case_sensitive: Whether search is case sensitive
        
        Returns:
            List of matching messages
        """
        if not case_sensitive:
            query = query.lower()
        
        matches = []
        for msg in session.messages:
            content = msg.content if case_sensitive else msg.content.lower()
            if query in content:
                matches.append(msg)
        
        return matches
    
    def get_conversation_summary_stats(self, session: ConversationSession) -> Dict:
        """
        Get summary statistics for conversation.
        
        Args:
            session: Conversation session
        
        Returns:
            Dictionary with statistics
        """
        user_messages = [msg for msg in session.messages if msg.role == "user"]
        assistant_messages = [msg for msg in session.messages if msg.role == "assistant"]
        
        return {
            'total_messages': len(session.messages),
            'user_messages': len(user_messages),
            'assistant_messages': len(assistant_messages),
            'images_shared': sum(len(msg.images) if msg.images else 0 for msg in session.messages),
            'documents_shared': sum(len(msg.documents) if msg.documents else 0 for msg in session.messages),
            'duration_hours': (session.updated_at - session.created_at).total_seconds() / 3600,
            'first_message': session.messages[0].timestamp.isoformat() if session.messages else None,
            'last_message': session.messages[-1].timestamp.isoformat() if session.messages else None
        }
