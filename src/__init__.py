"""
MedSight - AI-Powered Medical Assistant

A comprehensive, conversational, multi-modal medical AI assistant with 
healthcare-specific guardrails and multi-agent intelligence.

Version: 2.0.0
"""

__version__ = "2.0.0"
__author__ = "MedSight Team"
__description__ = "AI-Powered Medical Assistant with Multi-Agent Intelligence"

# Core imports for easy access
from .agents import Orchestrator, BaseAgent
from .models import PatientData, MedicalImage, MedicalRecord
from .guardrails import InputValidator, OutputValidator, SafetyChecker
from .conversation import SessionManager, ContextManager

__all__ = [
    'Orchestrator',
    'BaseAgent',
    'PatientData',
    'MedicalImage',
    'MedicalRecord',
    'InputValidator',
    'OutputValidator',
    'SafetyChecker',
    'SessionManager',
    'ContextManager',
]
