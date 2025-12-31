"""
Base Agent Class for MedSight Multi-Agent System

This module provides the abstract base class that all specialized agents inherit from.
It defines the common interface and shared functionality for all agents in the system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
from enum import Enum


class AgentType(Enum):
    """Enumeration of agent types in the system"""
    ROUTING = "routing"
    IMAGE_ANALYZER = "image_analyzer"
    RECORD_PARSER = "record_parser"
    SYNTHESIS = "synthesis"
    QA = "qa"
    ORCHESTRATOR = "orchestrator"


class AgentStatus(Enum):
    """Agent execution status"""
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING = "waiting"


class AgentResult:
    """
    Standardized result object returned by all agents
    """
    def __init__(
        self,
        success: bool,
        data: Any,
        confidence: float = 1.0,
        metadata: Optional[Dict] = None,
        error: Optional[str] = None,
        sources: Optional[List[str]] = None
    ):
        self.success = success
        self.data = data
        self.confidence = confidence
        self.metadata = metadata or {}
        self.error = error
        self.sources = sources or []
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict:
        """Convert result to dictionary"""
        return {
            "success": self.success,
            "data": self.data,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "error": self.error,
            "sources": self.sources,
            "timestamp": self.timestamp.isoformat()
        }


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the MedSight system.
    
    All specialized agents (ImageAnalyzerAgent, RecordParserAgent, etc.)
    must inherit from this class and implement the required abstract methods.
    """
    
    def __init__(
        self,
        agent_type: AgentType,
        name: str,
        config: Optional[Dict] = None
    ):
        """
        Initialize the base agent.
        
        Args:
            agent_type: Type of agent (from AgentType enum)
            name: Human-readable name for the agent
            config: Optional configuration dictionary
        """
        self.agent_type = agent_type
        self.name = name
        self.config = config or {}
        self.status = AgentStatus.IDLE
        self.logger = self._setup_logger()
        
        # Metrics tracking
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_processing_time": 0.0,
            "average_confidence": 0.0
        }
    
    def _setup_logger(self) -> logging.Logger:
        """Set up logging for the agent"""
        logger = logging.getLogger(f"medsight.agents.{self.name}")
        logger.setLevel(logging.INFO)
        
        # Create console handler if not already exists
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                f'%(asctime)s - {self.name} - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    @abstractmethod
    async def process(self, input_data: Any, context: Optional[Dict] = None) -> AgentResult:
        """
        Process input data and return results.
        
        This is the main method that each agent must implement.
        
        Args:
            input_data: Input data to process (type varies by agent)
            context: Optional context dictionary with additional information
        
        Returns:
            AgentResult object containing the processing results
        """
        pass
    
    @abstractmethod
    def validate_input(self, input_data: Any) -> bool:
        """
        Validate input data before processing.
        
        Args:
            input_data: Input data to validate
        
        Returns:
            True if input is valid, False otherwise
        """
        pass
    
    def pre_process(self, input_data: Any, context: Optional[Dict] = None) -> Any:
        """
        Pre-processing hook called before main processing.
        
        Can be overridden by subclasses for custom pre-processing.
        
        Args:
            input_data: Input data
            context: Optional context
        
        Returns:
            Processed input data
        """
        self.logger.info(f"Pre-processing input for {self.name}")
        return input_data
    
    def post_process(self, result: AgentResult) -> AgentResult:
        """
        Post-processing hook called after main processing.
        
        Can be overridden by subclasses for custom post-processing.
        
        Args:
            result: AgentResult from main processing
        
        Returns:
            Processed AgentResult
        """
        self.logger.info(f"Post-processing result for {self.name}")
        return result
    
    async def execute(self, input_data: Any, context: Optional[Dict] = None) -> AgentResult:
        """
        Main execution method that orchestrates the agent workflow.
        
        This method handles the complete agent execution lifecycle:
        1. Input validation
        2. Pre-processing
        3. Main processing
        4. Post-processing
        5. Metrics tracking
        
        Args:
            input_data: Input data to process
            context: Optional context dictionary
        
        Returns:
            AgentResult object
        """
        start_time = datetime.utcnow()
        self.status = AgentStatus.PROCESSING
        self.metrics["total_requests"] += 1
        
        try:
            # 1. Validate input
            if not self.validate_input(input_data):
                self.logger.error(f"Invalid input for {self.name}")
                self.status = AgentStatus.FAILED
                self.metrics["failed_requests"] += 1
                return AgentResult(
                    success=False,
                    data=None,
                    error="Invalid input data"
                )
            
            # 2. Pre-process
            processed_input = self.pre_process(input_data, context)
            
            # 3. Main processing
            self.logger.info(f"Processing request with {self.name}")
            result = await self.process(processed_input, context)
            
            # 4. Post-process
            final_result = self.post_process(result)
            
            # 5. Update metrics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.metrics["total_processing_time"] += processing_time
            
            if final_result.success:
                self.metrics["successful_requests"] += 1
                self.status = AgentStatus.COMPLETED
            else:
                self.metrics["failed_requests"] += 1
                self.status = AgentStatus.FAILED
            
            # Update average confidence
            if final_result.success:
                total_successful = self.metrics["successful_requests"]
                current_avg = self.metrics["average_confidence"]
                self.metrics["average_confidence"] = (
                    (current_avg * (total_successful - 1) + final_result.confidence) / total_successful
                )
            
            self.logger.info(
                f"{self.name} completed in {processing_time:.2f}s "
                f"(confidence: {final_result.confidence:.2f})"
            )
            
            return final_result
            
        except Exception as e:
            self.logger.error(f"Error in {self.name}: {str(e)}", exc_info=True)
            self.status = AgentStatus.FAILED
            self.metrics["failed_requests"] += 1
            
            return AgentResult(
                success=False,
                data=None,
                error=f"Agent execution failed: {str(e)}"
            )
        
        finally:
            if self.status != AgentStatus.PROCESSING:
                self.status = AgentStatus.IDLE
    
    def get_metrics(self) -> Dict:
        """
        Get agent performance metrics.
        
        Returns:
            Dictionary containing agent metrics
        """
        success_rate = 0.0
        if self.metrics["total_requests"] > 0:
            success_rate = (
                self.metrics["successful_requests"] / self.metrics["total_requests"]
            )
        
        avg_processing_time = 0.0
        if self.metrics["total_requests"] > 0:
            avg_processing_time = (
                self.metrics["total_processing_time"] / self.metrics["total_requests"]
            )
        
        return {
            "agent_name": self.name,
            "agent_type": self.agent_type.value,
            "status": self.status.value,
            "total_requests": self.metrics["total_requests"],
            "successful_requests": self.metrics["successful_requests"],
            "failed_requests": self.metrics["failed_requests"],
            "success_rate": success_rate,
            "average_processing_time": avg_processing_time,
            "average_confidence": self.metrics["average_confidence"]
        }
    
    def reset_metrics(self):
        """Reset agent metrics"""
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_processing_time": 0.0,
            "average_confidence": 0.0
        }
        self.logger.info(f"Metrics reset for {self.name}")
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
        
        Returns:
            Configuration value
        """
        return self.config.get(key, default)
    
    def update_config(self, key: str, value: Any):
        """
        Update configuration value.
        
        Args:
            key: Configuration key
            value: New value
        """
        self.config[key] = value
        self.logger.info(f"Updated config: {key} = {value}")
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', type={self.agent_type.value}, status={self.status.value})"
