"""Tests for session manager"""

import pytest
from src.conversation.session_manager import SessionManager
from src.models.message import Message, MessageRole


def test_create_session():
    """Test session creation"""
    manager = SessionManager()
    session_id = manager.create_session()
    
    assert session_id is not None
    assert len(session_id) > 0


def test_get_session():
    """Test getting a session"""
    manager = SessionManager()
    session_id = manager.create_session()
    session = manager.get_session(session_id)
    
    assert session is not None
    assert session.session_id == session_id


def test_add_message():
    """Test adding a message to a session"""
    manager = SessionManager()
    session_id = manager.create_session()
    
    message = Message(
        role=MessageRole.USER,
        content="Test message"
    )
    
    success = manager.add_message(session_id, message)
    assert success == True
    
    session = manager.get_session(session_id)
    assert len(session.messages) == 1
    assert session.messages[0].content == "Test message"


def test_delete_session():
    """Test deleting a session"""
    manager = SessionManager()
    session_id = manager.create_session()
    
    deleted = manager.delete_session(session_id)
    assert deleted == True
    
    session = manager.get_session(session_id)
    assert session is None


def test_get_all_sessions():
    """Test getting all sessions"""
    manager = SessionManager()
    session_id1 = manager.create_session()
    session_id2 = manager.create_session()
    
    all_sessions = manager.get_all_sessions()
    assert len(all_sessions) >= 2
    assert session_id1 in all_sessions
    assert session_id2 in all_sessions
