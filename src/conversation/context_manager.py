"""Context management for conversations"""

from typing import List, Dict, Optional, Any
import logging

from ..models.message import Message, ConversationSession


class ContextManager:
    """Manages conversation context and history"""
    
    def __init__(self, max_context_messages: int = 10):
        """
        Initialize context manager.
        
        Args:
            max_context_messages: Maximum messages to keep in context
        """
        self.logger = logging.getLogger(__name__)
        self.max_context_messages = max_context_messages
    
    def get_context(
        self,
        session: ConversationSession,
        include_images: bool = True,
        include_documents: bool = True
    ) -> Dict[str, Any]:
        """
        Get conversation context.
        
        Args:
            session: Conversation session
            include_images: Whether to include images in context
            include_documents: Whether to include documents in context
        
        Returns:
            Context dictionary
        """
        recent_messages = session.get_recent_messages(self.max_context_messages)
        
        context = {
            'session_id': session.session_id,
            'message_count': len(session.messages),
            'recent_messages': [],
            'images': [],
            'documents': [],
            'metadata': session.metadata
        }
        
        for msg in recent_messages:
            msg_dict = {
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat()
            }
            
            if include_images and msg.images:
                msg_dict['images'] = msg.images
                context['images'].extend(msg.images)
            
            if include_documents and msg.documents:
                msg_dict['documents'] = msg.documents
                context['documents'].extend(msg.documents)
            
            context['recent_messages'].append(msg_dict)
        
        return context
    
    def build_prompt_context(self, session: ConversationSession) -> str:
        """
        Build context string for model prompt.
        
        Args:
            session: Conversation session
        
        Returns:
            Context string
        """
        recent_messages = session.get_recent_messages(self.max_context_messages)
        
        context_parts = []
        context_parts.append("Previous conversation:")
        
        for msg in recent_messages[:-1]:  # Exclude the latest message
            role_label = "User" if msg.role == "user" else "Assistant"
            context_parts.append(f"{role_label}: {msg.content}")
        
        return "\n".join(context_parts)
    
    def extract_references(self, query: str, session: ConversationSession) -> List[Dict]:
        """
        Extract references to previous messages.
        
        Args:
            query: User query
            session: Conversation session
        
        Returns:
            List of referenced messages
        """
        references = []
        reference_keywords = [
            'previous', 'last', 'earlier', 'that', 'this',
            'the scan', 'the image', 'the finding'
        ]
        
        # Check if query contains reference keywords
        has_reference = any(keyword in query.lower() for keyword in reference_keywords)
        
        if has_reference and len(session.messages) > 0:
            # Return recent messages that might be referenced
            recent = session.get_recent_messages(3)
            for msg in recent:
                if msg.images or msg.documents:
                    references.append({
                        'role': msg.role,
                        'content': msg.content,
                        'has_images': bool(msg.images),
                        'has_documents': bool(msg.documents)
                    })
        
        return references
    
    def summarize_conversation(self, session: ConversationSession) -> str:
        """
        Create a summary of the conversation.
        
        Args:
            session: Conversation session
        
        Returns:
            Conversation summary
        """
        if len(session.messages) == 0:
            return "No conversation history."
        
        summary_parts = [
            f"Conversation started: {session.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"Total messages: {len(session.messages)}",
        ]
        
        # Count images and documents
        total_images = sum(len(msg.images) if msg.images else 0 for msg in session.messages)
        total_documents = sum(len(msg.documents) if msg.documents else 0 for msg in session.messages)
        
        if total_images > 0:
            summary_parts.append(f"Images analyzed: {total_images}")
        if total_documents > 0:
            summary_parts.append(f"Documents processed: {total_documents}")
        
        return " | ".join(summary_parts)
