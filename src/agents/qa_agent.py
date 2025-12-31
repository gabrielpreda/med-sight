"""QA Agent for handling follow-up questions"""

from typing import Any, Dict, List, Optional
import logging

from .base_agent import BaseAgent, AgentType, AgentResult


class QAAgent(BaseAgent):
    """
    Agent specialized in answering follow-up questions based on conversation history.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize QA agent"""
        super().__init__(
            agent_type=AgentType.QA,
            name="QAAgent",
            config=config
        )
    
    def validate_input(self, input_data: Any) -> bool:
        """Validate input"""
        if isinstance(input_data, dict):
            return 'query' in input_data
        return isinstance(input_data, str)
    
    async def process(self, input_data: Any, context: Optional[Dict] = None) -> AgentResult:
        """
        Answer follow-up questions using conversation context.
        
        Args:
            input_data: Dict with 'query' and optionally 'conversation_history'
            context: Optional context
        
        Returns:
            AgentResult with answer
        """
        try:
            # Extract query and history
            if isinstance(input_data, str):
                query = input_data
                conversation_history = context.get('conversation_history', []) if context else []
            else:
                query = input_data.get('query', '')
                conversation_history = input_data.get('conversation_history', [])
            
            # Find relevant context
            relevant_context = self._find_relevant_context(query, conversation_history)
            
            # Generate answer
            answer = self._generate_answer(query, relevant_context)
            
            # Determine if this is a medical term explanation
            is_explanation = self._is_explanation_request(query)
            
            # Calculate confidence
            confidence = self._calculate_confidence(relevant_context, is_explanation)
            
            return AgentResult(
                success=True,
                data={
                    'answer': answer,
                    'is_explanation': is_explanation,
                    'relevant_context': relevant_context
                },
                confidence=confidence,
                metadata={
                    'query_type': 'explanation' if is_explanation else 'follow_up',
                    'context_items': len(relevant_context)
                },
                sources=['Conversation History']
            )
            
        except Exception as e:
            self.logger.error(f"QA processing failed: {e}")
            return AgentResult(
                success=False,
                data=None,
                error=str(e)
            )
    
    def _find_relevant_context(self, query: str, conversation_history: List[Dict]) -> List[Dict]:
        """Find relevant context from conversation history"""
        relevant = []
        query_lower = query.lower()
        
        # Keywords that might indicate what the user is referring to
        reference_keywords = ['that', 'this', 'the', 'previous', 'earlier', 'last']
        
        # Check if query contains references
        has_reference = any(keyword in query_lower for keyword in reference_keywords)
        
        if has_reference:
            # Return recent messages (last 3)
            relevant = conversation_history[-3:] if len(conversation_history) >= 3 else conversation_history
        else:
            # Search for keyword matches
            keywords = query_lower.split()
            for msg in conversation_history:
                msg_content = msg.get('content', '').lower()
                if any(keyword in msg_content for keyword in keywords if len(keyword) > 3):
                    relevant.append(msg)
        
        return relevant
    
    def _generate_answer(self, query: str, relevant_context: List[Dict]) -> str:
        """Generate answer based on query and context"""
        query_lower = query.lower()
        
        # Check if this is a medical term explanation request
        if any(phrase in query_lower for phrase in ['what does', 'what is', 'explain', 'mean']):
            return self._explain_medical_term(query, relevant_context)
        
        # Check if asking about previous findings
        if any(phrase in query_lower for phrase in ['previous', 'earlier', 'last', 'that finding']):
            return self._answer_about_previous(query, relevant_context)
        
        # General follow-up
        if relevant_context:
            context_summary = self._summarize_context(relevant_context)
            return f"Based on our previous discussion: {context_summary}\n\nRegarding your question: {self._provide_general_answer(query)}"
        
        return self._provide_general_answer(query)
    
    def _explain_medical_term(self, query: str, relevant_context: List[Dict]) -> str:
        """Explain medical terms"""
        # Extract the term being asked about
        term = self._extract_term_from_query(query)
        
        # Common medical term explanations
        explanations = {
            'costophrenic angle': "The costophrenic angle is the sharp angle formed where the diaphragm meets the chest wall on an X-ray. Sharp angles are normal; blunted angles may indicate fluid accumulation (pleural effusion).",
            'infiltrate': "An infiltrate on imaging refers to an abnormal substance (like fluid, cells, or other material) that has accumulated in the lung tissue, often indicating infection, inflammation, or other pathology.",
            'consolidation': "Consolidation refers to a region of the lung that has filled with liquid instead of air, appearing white on X-rays. This is commonly seen in pneumonia.",
            'opacity': "Opacity refers to an area on an image that appears whiter or denser than normal, indicating increased tissue density or the presence of fluid or solid material.",
            'atelectasis': "Atelectasis is the partial or complete collapse of a lung or a section of lung, appearing as increased density on imaging.",
        }
        
        term_lower = term.lower()
        for key, explanation in explanations.items():
            if key in term_lower:
                # Add context from previous findings if available
                if relevant_context:
                    return f"{explanation}\n\nIn your case, this was mentioned in the context of the imaging findings we discussed."
                return explanation
        
        return f"I can provide general information about medical terms, but for specific interpretation of '{term}' in your case, please consult with your healthcare provider."
    
    def _answer_about_previous(self, query: str, relevant_context: List[Dict]) -> str:
        """Answer questions about previous findings"""
        if not relevant_context:
            return "I don't have enough context from our previous conversation to answer this question. Could you please provide more details?"
        
        # Summarize previous context
        summary = self._summarize_context(relevant_context)
        return f"Based on our previous discussion:\n\n{summary}\n\nIs there a specific aspect you'd like me to clarify?"
    
    def _provide_general_answer(self, query: str) -> str:
        """Provide a general answer"""
        return "I'd be happy to help answer your question. However, I need more context or information to provide a specific answer. Could you please provide more details or rephrase your question?"
    
    def _extract_term_from_query(self, query: str) -> str:
        """Extract the medical term being asked about"""
        # Simple extraction - look for quoted terms or terms after "what is/does"
        import re
        
        # Check for quoted terms
        quoted = re.search(r'["\']([^"\']+)["\']', query)
        if quoted:
            return quoted.group(1)
        
        # Check for "what is/does X" pattern
        pattern = r'what (?:is|does|are) (?:a |an |the )?([^?]+)'
        match = re.search(pattern, query.lower())
        if match:
            return match.group(1).strip()
        
        return query
    
    def _summarize_context(self, context: List[Dict]) -> str:
        """Summarize context messages"""
        summaries = []
        for msg in context:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if content:
                # Truncate long messages
                truncated = content[:200] + "..." if len(content) > 200 else content
                summaries.append(f"- {role.capitalize()}: {truncated}")
        
        return "\n".join(summaries) if summaries else "No previous context available."
    
    def _is_explanation_request(self, query: str) -> bool:
        """Check if query is requesting an explanation"""
        explanation_phrases = [
            'what does', 'what is', 'what are', 'explain', 'clarify',
            'tell me about', 'what do you mean', 'define'
        ]
        query_lower = query.lower()
        return any(phrase in query_lower for phrase in explanation_phrases)
    
    def _calculate_confidence(self, relevant_context: List[Dict], is_explanation: bool) -> float:
        """Calculate confidence in answer"""
        base_confidence = 0.6
        
        # Higher confidence for explanations (general medical knowledge)
        if is_explanation:
            base_confidence = 0.75
        
        # Increase confidence if we have relevant context
        if relevant_context:
            base_confidence += 0.1 * min(len(relevant_context), 3)
        
        return min(base_confidence, 0.9)
