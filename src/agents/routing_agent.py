"""Routing Agent for request classification and routing"""

from typing import Any, Dict, Optional
from enum import Enum
import logging

from .base_agent import BaseAgent, AgentType, AgentResult


class RequestType(str, Enum):
    """Types of requests the system can handle"""
    IMAGE_ANALYSIS = "image_analysis"
    RECORD_ANALYSIS = "record_analysis"
    COMPREHENSIVE_REVIEW = "comprehensive_review"
    FOLLOW_UP_QUESTION = "follow_up_question"
    EMERGENCY = "emergency"
    COMPARISON = "comparison"
    UNKNOWN = "unknown"


class RoutingAgent(BaseAgent):
    """
    Agent that classifies requests and routes them to appropriate handlers.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize routing agent"""
        super().__init__(
            agent_type=AgentType.ROUTING,
            name="RoutingAgent",
            config=config
        )
        
        # Keywords for classification
        self.classification_keywords = {
            RequestType.IMAGE_ANALYSIS: [
                'analyze', 'image', 'scan', 'x-ray', 'mri', 'ct',
                'what do you see', 'findings', 'abnormalities'
            ],
            RequestType.RECORD_ANALYSIS: [
                'record', 'history', 'document', 'report', 'notes',
                'previous diagnosis', 'medical history'
            ],
            RequestType.COMPREHENSIVE_REVIEW: [
                'combine', 'together', 'correlate', 'compare with history',
                'comprehensive', 'overall', 'complete analysis'
            ],
            RequestType.FOLLOW_UP_QUESTION: [
                'what does', 'explain', 'clarify', 'tell me more',
                'previous', 'earlier', 'that finding', 'the scan'
            ],
            RequestType.EMERGENCY: [
                'emergency', 'urgent', 'chest pain', 'difficulty breathing',
                'severe', 'critical', 'immediate'
            ],
            RequestType.COMPARISON: [
                'compare', 'difference', 'change', 'progression',
                'before and after', 'previous scan', 'last time'
            ]
        }
    
    def validate_input(self, input_data: Any) -> bool:
        """Validate routing input"""
        if isinstance(input_data, dict):
            return 'query' in input_data
        return isinstance(input_data, str)
    
    async def process(self, input_data: Any, context: Optional[Dict] = None) -> AgentResult:
        """
        Classify and route the request.
        
        Args:
            input_data: Dict with 'query', 'has_images', 'has_documents', etc.
            context: Optional context
        
        Returns:
            AgentResult with routing decision
        """
        try:
            # Extract query
            if isinstance(input_data, str):
                query = input_data
                has_images = False
                has_documents = False
                has_history = False
            else:
                query = input_data.get('query', '')
                has_images = input_data.get('has_images', False)
                has_documents = input_data.get('has_documents', False)
                has_history = input_data.get('has_history', False)
            
            # Classify request
            request_type = self._classify_request(
                query, has_images, has_documents, has_history
            )
            
            # Determine routing
            routing_decision = self._determine_routing(request_type, has_images, has_documents)
            
            return AgentResult(
                success=True,
                data={
                    'request_type': request_type.value,
                    'routing': routing_decision,
                    'priority': self._get_priority(request_type),
                    'requires_multi_agent': routing_decision.get('multi_agent', False)
                },
                confidence=routing_decision.get('confidence', 0.8),
                metadata={'query_length': len(query)}
            )
            
        except Exception as e:
            self.logger.error(f"Routing failed: {e}")
            return AgentResult(
                success=False,
                data=None,
                error=str(e)
            )
    
    def _classify_request(
        self,
        query: str,
        has_images: bool,
        has_documents: bool,
        has_history: bool
    ) -> RequestType:
        """Classify the type of request"""
        query_lower = query.lower()
        
        # Check for emergency first
        if any(keyword in query_lower for keyword in self.classification_keywords[RequestType.EMERGENCY]):
            return RequestType.EMERGENCY
        
        # Check for comprehensive review
        if (has_images and has_documents) or \
           any(keyword in query_lower for keyword in self.classification_keywords[RequestType.COMPREHENSIVE_REVIEW]):
            return RequestType.COMPREHENSIVE_REVIEW
        
        # Check for comparison
        if any(keyword in query_lower for keyword in self.classification_keywords[RequestType.COMPARISON]):
            return RequestType.COMPARISON
        
        # Check for follow-up question
        if has_history and any(keyword in query_lower for keyword in self.classification_keywords[RequestType.FOLLOW_UP_QUESTION]):
            return RequestType.FOLLOW_UP_QUESTION
        
        # Check for image analysis
        if has_images or any(keyword in query_lower for keyword in self.classification_keywords[RequestType.IMAGE_ANALYSIS]):
            return RequestType.IMAGE_ANALYSIS
        
        # Check for record analysis
        if has_documents or any(keyword in query_lower for keyword in self.classification_keywords[RequestType.RECORD_ANALYSIS]):
            return RequestType.RECORD_ANALYSIS
        
        return RequestType.UNKNOWN
    
    def _determine_routing(
        self,
        request_type: RequestType,
        has_images: bool,
        has_documents: bool
    ) -> Dict:
        """Determine which agents to route to"""
        routing = {
            'agents': [],
            'multi_agent': False,
            'confidence': 0.8
        }
        
        if request_type == RequestType.EMERGENCY:
            routing['agents'] = ['emergency_handler']
            routing['priority'] = 'urgent'
            routing['confidence'] = 0.95
            
        elif request_type == RequestType.IMAGE_ANALYSIS:
            routing['agents'] = ['image_analyzer']
            routing['confidence'] = 0.9
            
        elif request_type == RequestType.RECORD_ANALYSIS:
            routing['agents'] = ['record_parser']
            routing['confidence'] = 0.85
            
        elif request_type == RequestType.COMPREHENSIVE_REVIEW:
            routing['agents'] = ['image_analyzer', 'record_parser', 'synthesis']
            routing['multi_agent'] = True
            routing['confidence'] = 0.85
            
        elif request_type == RequestType.COMPARISON:
            routing['agents'] = ['image_analyzer', 'comparison']
            routing['multi_agent'] = True
            routing['confidence'] = 0.8
            
        elif request_type == RequestType.FOLLOW_UP_QUESTION:
            routing['agents'] = ['qa']
            routing['confidence'] = 0.75
            
        else:
            routing['agents'] = ['qa']
            routing['confidence'] = 0.5
        
        return routing
    
    def _get_priority(self, request_type: RequestType) -> str:
        """Get priority level for request type"""
        if request_type == RequestType.EMERGENCY:
            return 'urgent'
        elif request_type in [RequestType.COMPREHENSIVE_REVIEW, RequestType.IMAGE_ANALYSIS]:
            return 'high'
        else:
            return 'normal'
