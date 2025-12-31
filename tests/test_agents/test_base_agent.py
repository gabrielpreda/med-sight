"""Tests for base agent"""

import pytest
import asyncio
from src.agents.base_agent import BaseAgent, AgentType, AgentResult


class TestAgent(BaseAgent):
    """Test implementation of BaseAgent"""
    
    def __init__(self):
        super().__init__(
            agent_type=AgentType.QA,
            name="TestAgent"
        )
    
    def validate_input(self, input_data):
        return isinstance(input_data, str)
    
    async def process(self, input_data, context=None):
        return AgentResult(
            success=True,
            data=f"Processed: {input_data}",
            confidence=0.9
        )


@pytest.mark.asyncio
async def test_agent_initialization():
    """Test agent initialization"""
    agent = TestAgent()
    assert agent.name == "TestAgent"
    assert agent.agent_type == AgentType.QA


@pytest.mark.asyncio
async def test_agent_execution():
    """Test agent execution"""
    agent = TestAgent()
    result = await agent.execute("test input")
    
    assert result.success == True
    assert "Processed" in result.data
    assert result.confidence == 0.9


@pytest.mark.asyncio
async def test_agent_metrics():
    """Test agent metrics tracking"""
    agent = TestAgent()
    
    # Execute a few times
    await agent.execute("test 1")
    await agent.execute("test 2")
    
    metrics = agent.get_metrics()
    assert metrics['total_requests'] == 2
    assert metrics['successful_requests'] == 2
    assert metrics['failed_requests'] == 0


@pytest.mark.asyncio
async def test_agent_invalid_input():
    """Test agent with invalid input"""
    agent = TestAgent()
    result = await agent.execute(123)  # Invalid - not a string
    
    assert result.success == False
    assert result.error is not None
