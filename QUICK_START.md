# Quick Start Guide - Phase 1 Implementation

This guide will help you get started with Phase 1 of the MedSight transformation: **Foundation & Restructuring**.

---

## Prerequisites

Before starting, ensure you have:

- [x] Python 3.10 or higher installed
- [x] Git installed and configured
- [x] Google Cloud Project with Vertex AI enabled
- [x] MedGemma model deployed to an endpoint
- [x] Environment variables configured in `.env`

---

## Step 1: Backup Current Code

First, let's create a backup of your current working code:

```bash
cd /Users/gabrielpreda/workspace/my_projects/med-sight

# Create a backup branch
git checkout -b backup/pre-refactor
git add .
git commit -m "Backup before Phase 1 refactoring"

# Create new development branch
git checkout -b feature/phase-1-foundation
```

---

## Step 2: Install New Dependencies

Update your `requirements.txt` with the new dependencies:

```bash
# Add to requirements.txt (keep existing dependencies)
cat >> requirements.txt << 'EOF'

# Agentic Framework
langchain==0.1.0
langchain-google-vertexai==0.1.0
langgraph==0.0.20

# Data Validation
pydantic==2.5.0

# Async Support
aiofiles==23.2.1

# YAML Configuration
pyyaml==6.0.1

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
EOF

# Install new dependencies
pip install -r requirements.txt
```

---

## Step 3: Create New Directory Structure

Create the new modular structure:

```bash
# Create main source directories
mkdir -p src/{agents,guardrails,conversation,document_processing,models,utils,ui}

# Create subdirectories
mkdir -p src/guardrails/config
mkdir -p src/document_processing/{parsers,extractors,integrators}
mkdir -p src/ui/{components,styles}

# Create test directories
mkdir -p tests/{test_agents,test_guardrails,test_conversation,test_document_processing}

# Create docs directory
mkdir -p docs

# Create __init__.py files
touch src/__init__.py
touch src/agents/__init__.py
touch src/guardrails/__init__.py
touch src/conversation/__init__.py
touch src/document_processing/__init__.py
touch src/models/__init__.py
touch src/utils/__init__.py
touch src/ui/__init__.py
touch tests/__init__.py
```

---

## Step 4: Move Existing Code

Move the current `app.py` to the new structure:

```bash
# Copy current app.py to new location
cp app.py src/ui/app.py

# Keep the original for now (we'll remove it later)
# Don't delete app.py yet - we'll migrate it gradually
```

---

## Step 5: Copy Created Files

The following files have already been created. They should be in your project:

- ✅ `config/guardrails.yaml`
- ✅ `src/agents/base_agent.py`
- ✅ `src/agents/image_analyzer_agent.py`
- ✅ `ARCHITECTURE_RECOMMENDATIONS.md`
- ✅ `IMPLEMENTATION_ROADMAP.md`
- ✅ `PROJECT_SUMMARY.md`

Verify they exist:

```bash
ls -la config/guardrails.yaml
ls -la src/agents/base_agent.py
ls -la src/agents/image_analyzer_agent.py
ls -la ARCHITECTURE_RECOMMENDATIONS.md
ls -la IMPLEMENTATION_ROADMAP.md
ls -la PROJECT_SUMMARY.md
```

---

## Step 6: Create Data Models

Create the core data models:

### Create `src/models/message.py`:

```python
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
```

### Create `src/models/__init__.py`:

```python
"""Data models for MedSight"""

from .message import Message, MessageRole, ConversationSession

__all__ = ['Message', 'MessageRole', 'ConversationSession']
```

---

## Step 7: Create Basic Guardrails

### Create `src/guardrails/input_validator.py`:

```python
"""Input validation for healthcare safety"""

import re
from typing import Dict, List, Optional
import yaml
from pathlib import Path


class InputValidator:
    """Validates user input for safety and compliance"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize input validator.
        
        Args:
            config_path: Path to guardrails configuration file
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "guardrails.yaml"
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.input_config = self.config.get('input_validation', {})
    
    def validate_query(self, query: str) -> Dict:
        """
        Validate user query.
        
        Args:
            query: User's text query
        
        Returns:
            Dictionary with validation results
        """
        issues = []
        
        # Check length
        if len(query) < self.input_config.get('min_query_length', 3):
            issues.append("Query too short")
        
        if len(query) > self.input_config.get('max_query_length', 2000):
            issues.append("Query too long")
        
        # Check for blocked patterns
        blocked_patterns = self.input_config.get('blocked_patterns', [])
        for pattern in blocked_patterns:
            if pattern.lower() in query.lower():
                issues.append(f"Query contains blocked pattern: {pattern}")
        
        # Check for emergency keywords
        emergency_keywords = self.input_config.get('emergency_keywords', [])
        is_emergency = any(keyword.lower() in query.lower() for keyword in emergency_keywords)
        
        # Check for PII
        pii_detected = self._detect_pii(query)
        
        return {
            'valid': len(issues) == 0 and not pii_detected,
            'issues': issues,
            'is_emergency': is_emergency,
            'pii_detected': pii_detected,
            'pii_types': self._get_pii_types(query) if pii_detected else []
        }
    
    def _detect_pii(self, text: str) -> bool:
        """Detect personally identifiable information"""
        pii_patterns = self.input_config.get('pii_patterns', [])
        
        for pattern_config in pii_patterns:
            pattern = pattern_config.get('regex', '')
            if re.search(pattern, text):
                return True
        
        return False
    
    def _get_pii_types(self, text: str) -> List[str]:
        """Get types of PII detected"""
        pii_types = []
        pii_patterns = self.input_config.get('pii_patterns', [])
        
        for pattern_config in pii_patterns:
            pattern = pattern_config.get('regex', '')
            pii_type = pattern_config.get('type', 'unknown')
            if re.search(pattern, text):
                pii_types.append(pii_type)
        
        return pii_types
```

### Create `src/guardrails/__init__.py`:

```python
"""Healthcare guardrails for MedSight"""

from .input_validator import InputValidator

__all__ = ['InputValidator']
```

---

## Step 8: Create Session Manager

### Create `src/conversation/session_manager.py`:

```python
"""Session management for conversations"""

import uuid
from typing import Dict, Optional
from datetime import datetime

from ..models.message import ConversationSession, Message


class SessionManager:
    """Manages conversation sessions"""
    
    def __init__(self):
        """Initialize session manager"""
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
            return True
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
            return True
        return False
```

### Create `src/conversation/__init__.py`:

```python
"""Conversation management for MedSight"""

from .session_manager import SessionManager

__all__ = ['SessionManager']
```

---

## Step 9: Create Basic Tests

### Create `tests/test_guardrails/test_input_validator.py`:

```python
"""Tests for input validator"""

import pytest
from src.guardrails.input_validator import InputValidator


def test_input_validator_initialization():
    """Test that input validator initializes correctly"""
    validator = InputValidator()
    assert validator is not None
    assert validator.config is not None


def test_valid_query():
    """Test validation of a valid query"""
    validator = InputValidator()
    result = validator.validate_query("Analyze this chest X-ray")
    
    assert result['valid'] == True
    assert len(result['issues']) == 0
    assert result['is_emergency'] == False


def test_emergency_detection():
    """Test emergency keyword detection"""
    validator = InputValidator()
    result = validator.validate_query("I have severe chest pain")
    
    assert result['is_emergency'] == True


def test_blocked_pattern():
    """Test blocked pattern detection"""
    validator = InputValidator()
    result = validator.validate_query("Can you prescribe medication for me?")
    
    assert result['valid'] == False
    assert len(result['issues']) > 0


def test_query_too_short():
    """Test query length validation - too short"""
    validator = InputValidator()
    result = validator.validate_query("Hi")
    
    assert result['valid'] == False
    assert "too short" in str(result['issues']).lower()
```

### Create `tests/test_conversation/test_session_manager.py`:

```python
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
```

---

## Step 10: Run Tests

Run the tests to verify everything is working:

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html  # On Mac
# or
xdg-open htmlcov/index.html  # On Linux
```

---

## Step 11: Update README

Update your `README.md` to reflect the new structure:

```markdown
# MedSight - AI-Powered Medical Image Analysis

MedSight is a conversational, multi-modal medical AI assistant that combines medical image analysis with clinical records for comprehensive patient insights.

## Features

- 🏥 **Healthcare Guardrails**: Built-in safety measures and HIPAA compliance
- 💬 **Conversational Interface**: Multi-turn dialogue with context awareness
- 🤖 **Multi-Agent System**: Specialized agents for different medical tasks
- 📄 **Multi-Modal Processing**: Combines images with medical records
- ⚕️ **Medical Safety**: Automatic disclaimers, emergency detection, confidence scoring

## Project Structure

```
med-sight/
├── src/                    # Source code
│   ├── agents/            # Multi-agent system
│   ├── guardrails/        # Healthcare safety
│   ├── conversation/      # Conversation management
│   └── ui/                # User interface
├── config/                # Configuration files
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## Quick Start

See [QUICK_START.md](QUICK_START.md) for detailed setup instructions.

## Documentation

- [Architecture Recommendations](ARCHITECTURE_RECOMMENDATIONS.md)
- [Implementation Roadmap](IMPLEMENTATION_ROADMAP.md)
- [Project Summary](PROJECT_SUMMARY.md)

## License

See [LICENSE](LICENSE) file.
```

---

## Step 12: Commit Your Changes

```bash
# Add all new files
git add .

# Commit
git commit -m "Phase 1: Foundation and restructuring

- Created modular project structure
- Implemented base agent framework
- Added healthcare guardrails
- Set up conversation management
- Created data models
- Added comprehensive tests"

# Push to remote
git push origin feature/phase-1-foundation
```

---

## Next Steps

After completing Phase 1, you can:

1. **Review and Test**: Thoroughly test the new structure
2. **Migrate UI**: Gradually migrate `app.py` to use new components
3. **Phase 2**: Start implementing the remaining agents
4. **Documentation**: Add more detailed documentation

---

## Troubleshooting

### Import Errors

If you get import errors, make sure:
- You're in the project root directory
- Your virtual environment is activated
- All `__init__.py` files are created
- Dependencies are installed

### Configuration Not Found

If guardrails configuration is not found:
```bash
# Verify the file exists
ls -la config/guardrails.yaml

# Check the path in input_validator.py
```

### Tests Failing

If tests fail:
```bash
# Run with verbose output
pytest tests/ -v -s

# Run a specific test
pytest tests/test_guardrails/test_input_validator.py -v
```

---

## Getting Help

If you encounter issues:

1. Check the [ARCHITECTURE_RECOMMENDATIONS.md](ARCHITECTURE_RECOMMENDATIONS.md)
2. Review the [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md)
3. Check test output for specific errors
4. Review the example implementations in `src/agents/`

---

**Phase 1 Complete!** 🎉

You now have a solid foundation for building the advanced MedSight system.
