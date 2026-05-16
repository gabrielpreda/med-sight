"""
MedSight Agents Package

Exports the ADK-based root agent as the primary interface.
Legacy ad-hoc agents are kept for reference but not used by default.
"""

from .adk_agents import root_agent  # noqa: F401

__all__ = ["root_agent"]
