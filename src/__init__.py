"""
MedSight - AI-Powered Medical Assistant

Version: 3.0.0 (ADK Edition)
"""

__version__ = "3.0.0"
__author__ = "MedSight Team"
__description__ = "AI-Powered Medical Assistant — Google ADK Multi-Agent System"

# Core ADK agent
from .agents import root_agent  # noqa: F401

# Data models (still used by UI)
from .models import PatientData, MedicalImage, MedicalRecord  # noqa: F401

__all__ = [
    "root_agent",
    "PatientData",
    "MedicalImage",
    "MedicalRecord",
]
