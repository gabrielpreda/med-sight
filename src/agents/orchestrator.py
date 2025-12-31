"""Orchestrator Agent - coordinates all agents and implements reflexion loop"""

from typing import Any, Dict, List, Optional
import logging
from google.cloud import aiplatform

from .base_agent import BaseAgent, AgentType, AgentResult
from .routing_agent import RoutingAgent, RequestType
from .image_analyzer_agent import ImageAnalyzerAgent, MedicalImageData
from .record_parser_agent import RecordParserAgent
from .synthesis_agent import SynthesisAgent
from .qa_agent import QAAgent

from ..guardrails import InputValidator, OutputValidator, SafetyChecker
from ..models import PatientData, AnalysisContext


class Orchestrator(BaseAgent):
    """
    Main orchestrator that coordinates all agents and implements reflexion loop.
    """
    
    def __init__(
        self,
        endpoint: aiplatform.Endpoint,
        config: Optional[Dict] = None
    ):
        """
        Initialize orchestrator.
        
        Args:
            endpoint: Vertex AI endpoint for MedGemma
            config: Optional configuration
        """
        super().__init__(
            agent_type=AgentType.ORCHESTRATOR,
            name="Orchestrator",
            config=config
        )
        
        # Initialize guardrails
        self.input_validator = InputValidator()
        self.output_validator = OutputValidator()
        self.safety_checker = SafetyChecker()
        
        # Initialize agents
        self.routing_agent = RoutingAgent()
        self.image_analyzer = ImageAnalyzerAgent(endpoint)
        self.record_parser = RecordParserAgent()
        self.synthesis_agent = SynthesisAgent()
        self.qa_agent = QAAgent()
        
        self.logger.info("Orchestrator initialized with all agents")
    
    def validate_input(self, input_data: Any) -> bool:
        """Validate orchestrator input"""
        if not isinstance(input_data, dict):
            return False
        return 'query' in input_data
    
    async def process(self, input_data: Any, context: Optional[Dict] = None) -> AgentResult:
        """
        Main orchestration process with reflexion loop.
        
        Args:
            input_data: Dict with 'query', 'patient_data', etc.
            context: Optional context
        
        Returns:
            AgentResult with final response
        """
        try:
            # Extract input
            query = input_data.get('query', '')
            patient_data = input_data.get('patient_data')
            conversation_history = input_data.get('conversation_history', [])
            
            # Step 1: Input Validation (Guardrails)
            validation_result = self.input_validator.validate_query(query)
            
            if not validation_result.valid:
                return AgentResult(
                    success=False,
                    data=None,
                    error=f"Input validation failed: {', '.join(validation_result.issues)}"
                )
            
            # Handle emergency
            if validation_result.is_emergency:
                return self._handle_emergency(query)
            
            # Step 2: Route Request
            routing_input = {
                'query': query,
                'has_images': patient_data and len(patient_data.images) > 0 if patient_data else False,
                'has_documents': patient_data and len(patient_data.records) > 0 if patient_data else False,
                'has_history': len(conversation_history) > 0
            }
            
            routing_result = await self.routing_agent.execute(routing_input)
            
            if not routing_result.success:
                return routing_result
            
            request_type = routing_result.data.get('request_type')
            routing_decision = routing_result.data.get('routing', {})
            
            # Step 3: Execute Appropriate Workflow
            if routing_decision.get('multi_agent', False):
                # Multi-agent workflow
                result = await self._execute_multi_agent_workflow(
                    query, patient_data, routing_decision
                )
            else:
                # Single agent workflow
                result = await self._execute_single_agent_workflow(
                    query, patient_data, conversation_history, routing_decision
                )
            
            if not result.success:
                return result
            
            # Step 4: Reflexion Loop (Self-Critique and Refinement)
            if self.config.get('enable_reflexion', True):
                result = await self._reflexion_loop(result, query, patient_data)
            
            # Step 5: Output Validation and Safety Check
            output_text = result.data.get('answer', '') if isinstance(result.data, dict) else str(result.data)
            
            safety_check = self.safety_checker.check_safety(
                output_text,
                result.confidence,
                validation_result.is_emergency
            )
            
            # Step 6: Add Disclaimers and Format Output
            
            # Determine appropriate disclaimer type
            disclaimer_type = 'general'
            if request_type == 'image_analysis':
                disclaimer_type = 'diagnostic'
            elif request_type == 'emergency':
                disclaimer_type = 'emergency'
                
            formatted_output = self.output_validator.format_medical_output(
                output_text,
                confidence=result.confidence,
                disclaimer_type=disclaimer_type,
                is_emergency=validation_result.is_emergency
            )
            
            # Update result with formatted output
            if isinstance(result.data, dict):
                result.data['answer'] = formatted_output
                result.data['safety_check'] = safety_check
            
            return result
            
        except Exception as e:
            self.logger.error(f"Orchestration failed: {e}", exc_info=True)
            return AgentResult(
                success=False,
                data=None,
                error=f"Orchestration failed: {str(e)}"
            )
    
    async def _execute_single_agent_workflow(
        self,
        query: str,
        patient_data: Optional[PatientData],
        conversation_history: List[Dict],
        routing_decision: Dict
    ) -> AgentResult:
        """Execute single agent workflow"""
        agents = routing_decision.get('agents', [])
        
        if not agents:
            return AgentResult(success=False, data=None, error="No agent specified")
        
        agent_name = agents[0]
        
        # Route to appropriate agent
        if agent_name == 'image_analyzer' and patient_data and patient_data.images:
            # Analyze most recent image
            image = patient_data.images[-1]
            image_data = MedicalImageData(
                image=image.to_pil_image(),
                image_type=image.image_type
            )
            result = await self.image_analyzer.execute({'image': image_data.image, 'query': query})
            
            # Format result
            if result.success:
                result.data = {'answer': self._format_image_analysis(result.data)}
            
            return result
        
        elif agent_name == 'record_parser' and patient_data and patient_data.records:
            # Parse most recent record
            record = patient_data.records[-1]
            result = await self.record_parser.execute(record)
            
            # Format result
            if result.success:
                result.data = {'answer': self._format_record_analysis(result.data)}
            
            return result
        
        elif agent_name == 'qa':
            # QA agent
            qa_input = {
                'query': query,
                'conversation_history': conversation_history
            }
            result = await self.qa_agent.execute(qa_input)
            
            return result
        
        else:
            return AgentResult(
                success=False,
                data=None,
                error=f"Agent '{agent_name}' not available or insufficient data"
            )
    
    async def _execute_multi_agent_workflow(
        self,
        query: str,
        patient_data: Optional[PatientData],
        routing_decision: Dict
    ) -> AgentResult:
        """Execute multi-agent workflow with synthesis"""
        results = {}
        
        # Execute image analyzer if needed
        if patient_data and patient_data.images:
            image = patient_data.images[-1]
            image_data = MedicalImageData(
                image=image.to_pil_image(),
                image_type=image.image_type
            )
            image_result = await self.image_analyzer.execute({'image': image_data.image, 'query': query})
            if image_result.success:
                results['image_findings'] = image_result.data
        
        # Execute record parser if needed
        if patient_data and patient_data.records:
            record = patient_data.records[-1]
            record_result = await self.record_parser.execute(record)
            if record_result.success:
                results['record_data'] = record_result.data
        
        # Synthesize results
        if len(results) >= 2:
            results['query'] = query
            synthesis_result = await self.synthesis_agent.execute(results)
            
            if synthesis_result.success:
                synthesis_result.data = {
                    'answer': synthesis_result.data.get('comprehensive_report', '')
                }
            
            return synthesis_result
        
        # If we only have one result, return it
        elif results:
            key = list(results.keys())[0]
            return AgentResult(
                success=True,
                data={'answer': self._format_single_result(results[key])},
                confidence=0.75
            )
        
        return AgentResult(
            success=False,
            data=None,
            error="Insufficient data for multi-agent analysis"
        )
    
    async def _reflexion_loop(
        self,
        result: AgentResult,
        query: str,
        patient_data: Optional[PatientData]
    ) -> AgentResult:
        """
        Implement reflexion loop for self-critique and refinement.
        
        Args:
            result: Initial result
            query: Original query
            patient_data: Patient data
        
        Returns:
            Refined result
        """
        # Check if refinement is needed
        if result.confidence >= 0.85:
            self.logger.info("High confidence - skipping reflexion")
            return result
        
        self.logger.info("Running reflexion loop for quality improvement")
        
        # Self-critique: Check for issues
        critique = self._critique_result(result, query)
        
        if critique['needs_refinement']:
            self.logger.info(f"Refinement needed: {critique['issues']}")
            
            # For now, just add a note about uncertainty
            # In production, this could trigger re-analysis or additional checks
            if isinstance(result.data, dict) and 'answer' in result.data:
                result.data['answer'] += "\n\n*Note: This analysis has moderate confidence and should be reviewed by a healthcare professional.*"
                result.data['refinement_notes'] = critique['issues']
        
        return result
    
    def _critique_result(self, result: AgentResult, query: str) -> Dict:
        """Critique the result for potential issues"""
        issues = []
        needs_refinement = False
        
        # Check confidence
        if result.confidence < 0.65:
            issues.append("Low confidence score")
            needs_refinement = True
        
        # Check for completeness
        if isinstance(result.data, dict):
            answer = result.data.get('answer', '')
            if len(answer) < 50:
                issues.append("Response may be too brief")
                needs_refinement = True
        
        return {
            'needs_refinement': needs_refinement,
            'issues': issues
        }
    
    def _handle_emergency(self, query: str) -> AgentResult:
        """Handle emergency situations"""
        emergency_response = """
🚨 EMERGENCY DETECTED 🚨

Your query suggests a potential medical emergency. This AI system is NOT appropriate for emergency medical situations.

IMMEDIATE ACTIONS REQUIRED:
1. Call 911 (or your local emergency number) immediately
2. Go to the nearest emergency room
3. Do not delay seeking immediate medical attention

This system cannot provide emergency medical care or advice.
"""
        
        return AgentResult(
            success=True,
            data={'answer': emergency_response},
            confidence=1.0,
            metadata={'is_emergency': True}
        )
    
    def _format_image_analysis(self, data: Dict) -> str:
        """Format image analysis results"""
        summary = data.get('summary', '')
        findings = data.get('detailed_findings', [])
        abnormalities = data.get('abnormalities', [])
        
        output = f"**IMAGING ANALYSIS**\n\n{summary}\n\n"
        
        if findings:
            output += "**Detailed Findings:**\n"
            for finding in findings[:5]:  # Limit to 5
                output += f"- {finding.get('finding', '')}\n"
        
        if abnormalities:
            output += "\n**Abnormalities Detected:**\n"
            for abnorm in abnormalities[:5]:
                output += f"- {abnorm.get('description', '')}\n"
        
        return output
    
    def _format_record_analysis(self, data: Dict) -> str:
        """Format record analysis results"""
        summary = data.get('summary', '')
        diagnoses = data.get('diagnoses', [])
        medications = data.get('medications', [])
        procedures = data.get('procedures', [])
        dates = data.get('dates', [])
        entities = data.get('entities', [])
        
        output = f"**MEDICAL RECORD ANALYSIS**\n\n"
        
        if summary and summary != "No structured information extracted.":
            output += f"{summary}\n\n"
        
        if diagnoses:
            output += "**Documented Diagnoses:**\n"
            for diag in diagnoses[:5]:
                output += f"- {diag}\n"
            output += "\n"
        
        if medications:
            output += "**Current Medications:**\n"
            for med in medications[:5]:
                output += f"- {med}\n"
            output += "\n"
            
        if procedures:
            output += "**Procedures:**\n"
            for proc in procedures[:5]:
                output += f"- {proc}\n"
            output += "\n"
            
        # Fallback: if no high-level info but we have dates or entities, show them
        if not (diagnoses or medications or procedures):
            if dates:
                output += "**Key Dates Mentioned:**\n"
                for date in sorted(dates)[:5]:
                    output += f"- {date}\n"
                output += "\n"
            
            # Show other entities if nothing else
            if not dates and entities:
                output += "**Extracted Entities:**\n"
                seen = set()
                for entity in entities[:10]:
                    txt = entity.get('text', '')
                    if txt and txt not in seen:
                        output += f"- {entity.get('entity_type', 'Entity')}: {txt}\n"
                        seen.add(txt)
                output += "\n"
                
            if summary == "No structured information extracted." and not dates and not entities:
                output += "No specific medical entities found. The document appears to contain narrative text: \n"
                # We don't have the original content here easily, but we can advise
                output += "*The parser analyzed the text but found no standard medical headers or keywords.*"

        return output
    
    def _format_single_result(self, data: Any) -> str:
        """Format a single result"""
        if isinstance(data, dict):
            if 'summary' in data:
                return data['summary']
            return str(data)
        return str(data)
