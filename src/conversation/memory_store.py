"""Memory store for conversation persistence"""

from typing import Dict, Optional, List
import json
from pathlib import Path
import logging
from datetime import datetime

from ..models.message import ConversationSession, Message, MessageRole


class MemoryStore:
    """Stores and retrieves conversation history"""
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize memory store.
        
        Args:
            storage_path: Path to storage directory
        """
        self.logger = logging.getLogger(__name__)
        
        if storage_path is None:
            storage_path = Path.home() / ".medsight" / "conversations"
        
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Memory store initialized at: {self.storage_path}")
    
    def save_session(self, session: ConversationSession) -> bool:
        """
        Save conversation session to disk.
        
        Args:
            session: Conversation session to save
        
        Returns:
            True if successful
        """
        try:
            file_path = self.storage_path / f"{session.session_id}.json"
            
            # Convert session to dict
            session_data = {
                'session_id': session.session_id,
                'user_id': session.user_id,
                'created_at': session.created_at.isoformat(),
                'updated_at': session.updated_at.isoformat(),
                'metadata': session.metadata,
                'messages': [
                    {
                        'role': msg.role,
                        'content': msg.content,
                        'timestamp': msg.timestamp.isoformat(),
                        'images': msg.images,
                        'documents': msg.documents,
                        'metadata': msg.metadata
                    }
                    for msg in session.messages
                ]
            }
            
            with open(file_path, 'w') as f:
                json.dump(session_data, f, indent=2)
            
            self.logger.debug(f"Saved session: {session.session_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save session: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        Load conversation session from disk.
        
        Args:
            session_id: Session identifier
        
        Returns:
            ConversationSession or None if not found
        """
        try:
            file_path = self.storage_path / f"{session_id}.json"
            
            if not file_path.exists():
                self.logger.warning(f"Session file not found: {session_id}")
                return None
            
            with open(file_path, 'r') as f:
                session_data = json.load(f)
            
            # Reconstruct messages
            messages = []
            for msg_data in session_data.get('messages', []):
                messages.append(Message(
                    role=MessageRole(msg_data['role']),
                    content=msg_data['content'],
                    timestamp=datetime.fromisoformat(msg_data['timestamp']),
                    images=msg_data.get('images'),
                    documents=msg_data.get('documents'),
                    metadata=msg_data.get('metadata', {})
                ))
            
            # Reconstruct session
            session = ConversationSession(
                session_id=session_data['session_id'],
                user_id=session_data.get('user_id'),
                messages=messages,
                created_at=datetime.fromisoformat(session_data['created_at']),
                updated_at=datetime.fromisoformat(session_data['updated_at']),
                metadata=session_data.get('metadata', {})
            )
            
            self.logger.debug(f"Loaded session: {session_id}")
            return session
            
        except Exception as e:
            self.logger.error(f"Failed to load session: {e}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete session from disk.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if deleted
        """
        try:
            file_path = self.storage_path / f"{session_id}.json"
            
            if file_path.exists():
                file_path.unlink()
                self.logger.info(f"Deleted session file: {session_id}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to delete session: {e}")
            return False
    
    def list_sessions(self) -> List[str]:
        """
        List all stored session IDs.
        
        Returns:
            List of session IDs
        """
        try:
            session_files = self.storage_path.glob("*.json")
            return [f.stem for f in session_files]
        except Exception as e:
            self.logger.error(f"Failed to list sessions: {e}")
            return []
    
    def cleanup_old_sessions(self, max_age_days: int = 90):
        """
        Clean up old session files.
        
        Args:
            max_age_days: Maximum age in days
        """
        try:
            current_time = datetime.utcnow()
            deleted_count = 0
            
            for session_file in self.storage_path.glob("*.json"):
                # Check file modification time
                file_time = datetime.fromtimestamp(session_file.stat().st_mtime)
                age_days = (current_time - file_time).days
                
                if age_days > max_age_days:
                    session_file.unlink()
                    deleted_count += 1
            
            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old session files")
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup sessions: {e}")
