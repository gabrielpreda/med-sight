"""Session management for conversations"""

import uuid
from typing import Dict, Optional
from datetime import datetime
import logging

from ..models.message import ConversationSession, Message


class SessionManager:
    """Manages conversation sessions"""
    
    def __init__(self):
        """Initialize session manager"""
        self.logger = logging.getLogger(__name__)
        self.sessions: Dict[str, ConversationSession] = {}
    
    def create_session(self, user_id: Optional[str] = None) -> str:
        """
        Create a new conversation session.
        
        Args:
            user_id: Optional user identifier
        
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        session = ConversationSession(
            session_id=session_id,
            user_id=user_id
        )
        self.sessions[session_id] = session
        self.logger.info(f"Created new session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        Get a conversation session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            ConversationSession or None if not found
        """
        return self.sessions.get(session_id)
    
    def add_message(self, session_id: str, message: Message) -> bool:
        """
        Add a message to a session.
        
        Args:
            session_id: Session identifier
            message: Message to add
        
        Returns:
            True if successful, False otherwise
        """
        session = self.get_session(session_id)
        if session:
            session.add_message(message)
            self.logger.debug(f"Added message to session {session_id}")
            return True
        self.logger.warning(f"Session not found: {session_id}")
        return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a conversation session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if deleted, False if not found
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            self.logger.info(f"Deleted session: {session_id}")
            return True
        return False
    
    def get_all_sessions(self) -> Dict[str, ConversationSession]:
        """Get all active sessions"""
        return self.sessions.copy()
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """
        Clean up old sessions.
        
        Args:
            max_age_hours: Maximum age in hours
        """
        current_time = datetime.utcnow()
        sessions_to_delete = []
        
        for session_id, session in self.sessions.items():
            age = (current_time - session.created_at).total_seconds() / 3600
            if age > max_age_hours:
                sessions_to_delete.append(session_id)
        
        for session_id in sessions_to_delete:
            self.delete_session(session_id)
        
        if sessions_to_delete:
            self.logger.info(f"Cleaned up {len(sessions_to_delete)} old sessions")
