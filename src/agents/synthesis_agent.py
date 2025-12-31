"""Synthesis Agent for combining multi-modal information"""

from typing import Any, Dict, List, Optional
import logging

from .base_agent import BaseAgent, AgentType, AgentResult


class SynthesisAgent(BaseAgent):
    """
    Agent that synthesizes information from multiple sources (images + records).
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize synthesis agent"""
        super().__init__(
            agent_type=AgentType.SYNTHESIS,
            name="SynthesisAgent",
            config=config
        )
    
    def validate_input(self, input_data: Any) -> bool:
        """Validate input - should have multiple data sources"""
        if not isinstance(input_data, dict):
            return False
        
        # Should have at least two sources
        has_image_findings = 'image_findings' in input_data
        has_record_data = 'record_data' in input_data
        
        return has_image_findings or has_record_data
    
    async def process(self, input_data: Any, context: Optional[Dict] = None) -> AgentResult:
        """
        Synthesize information from multiple sources.
        
        Args:
            input_data: Dict with 'image_findings', 'record_data', etc.
            context: Optional context
        
        Returns:
            AgentResult with synthesized report
        """
        try:
            image_findings = input_data.get('image_findings', {})
            record_data = input_data.get('record_data', {})
            query = input_data.get('query', '')
            
            # Generate synthesis
            synthesis = self._synthesize_findings(image_findings, record_data, query)
            
            # Identify correlations
            correlations = self._find_correlations(image_findings, record_data)
            
            # Identify discrepancies
            discrepancies = self._find_discrepancies(image_findings, record_data)
            
            # Generate comprehensive report
            report = self._generate_report(synthesis, correlations, discrepancies)
            
            # Calculate confidence
            confidence = self._calculate_synthesis_confidence(
                image_findings, record_data, correlations, discrepancies
            )
            
            return AgentResult(
                success=True,
                data={
                    'synthesis': synthesis,
                    'correlations': correlations,
                    'discrepancies': discrepancies,
                    'comprehensive_report': report
                },
                confidence=confidence,
                metadata={
                    'sources_count': sum([
                        1 if image_findings else 0,
                        1 if record_data else 0
                    ])
                },
                sources=['Image Analysis', 'Medical Records']
            )
            
        except Exception as e:
            self.logger.error(f"Synthesis failed: {e}")
            return AgentResult(
                success=False,
                data=None,
                error=str(e)
            )
    
    def _synthesize_findings(
        self,
        image_findings: Dict,
        record_data: Dict,
        query: str
    ) -> str:
        """Synthesize findings from multiple sources"""
        synthesis_parts = []
        
        # Add image findings summary
        if image_findings and 'summary' in image_findings:
            synthesis_parts.append(f"**Imaging Findings:**\n{image_findings['summary']}")
        
        # Add record data summary
        if record_data and 'summary' in record_data:
            synthesis_parts.append(f"\n**Clinical History:**\n{record_data['summary']}")
        
        # Add integrated analysis
        if image_findings and record_data:
            integration = self._integrate_findings(image_findings, record_data)
            synthesis_parts.append(f"\n**Integrated Analysis:**\n{integration}")
        
        return "\n".join(synthesis_parts) if synthesis_parts else "Insufficient data for synthesis."
    
    def _integrate_findings(self, image_findings: Dict, record_data: Dict) -> str:
        """Integrate findings from images and records"""
        integration_parts = []
        
        # Check for consistency
        image_abnormalities = image_findings.get('abnormalities', [])
        record_diagnoses = record_data.get('diagnoses', [])
        
        if image_abnormalities and record_diagnoses:
            integration_parts.append(
                "The imaging findings should be correlated with the documented clinical history."
            )
        
        # Add contextual interpretation
        if record_data.get('medications'):
            integration_parts.append(
                "Current medications and treatment history should be considered when interpreting imaging findings."
            )
        
        return " ".join(integration_parts) if integration_parts else "Limited integration possible with available data."
    
    def _find_correlations(self, image_findings: Dict, record_data: Dict) -> List[Dict]:
        """Find correlations between image findings and medical records"""
        correlations = []
        
        # Simple keyword-based correlation (in production, use more sophisticated NLP)
        image_text = str(image_findings).lower()
        record_text = str(record_data).lower()
        
        common_terms = ['pneumonia', 'fracture', 'mass', 'infiltrate', 'consolidation']
        
        for term in common_terms:
            if term in image_text and term in record_text:
                correlations.append({
                    'finding': term,
                    'correlation': 'confirmed',
                    'description': f"{term.capitalize()} noted in both imaging and clinical history"
                })
        
        return correlations
    
    def _find_discrepancies(self, image_findings: Dict, record_data: Dict) -> List[Dict]:
        """Find discrepancies between sources"""
        discrepancies = []
        
        # Check for contradictions
        # This is a simplified version - production would use more sophisticated logic
        
        image_summary = image_findings.get('summary', '').lower()
        record_summary = record_data.get('summary', '').lower()
        
        # Check for "normal" vs "abnormal" contradictions
        if 'normal' in image_summary and 'abnormal' in record_summary:
            discrepancies.append({
                'type': 'finding_mismatch',
                'description': 'Imaging appears normal but clinical history suggests abnormality',
                'requires_review': True
            })
        
        return discrepancies
    
    def _generate_report(
        self,
        synthesis: str,
        correlations: List[Dict],
        discrepancies: List[Dict]
    ) -> str:
        """Generate comprehensive report"""
        report_parts = [synthesis]
        
        if correlations:
            report_parts.append("\n**Correlations:**")
            for corr in correlations:
                report_parts.append(f"- {corr['description']}")
        
        if discrepancies:
            report_parts.append("\n**⚠️ Discrepancies Noted:**")
            for disc in discrepancies:
                report_parts.append(f"- {disc['description']}")
            report_parts.append("\n*These discrepancies require clinical correlation and review.*")
        
        return "\n".join(report_parts)
    
    def _calculate_synthesis_confidence(
        self,
        image_findings: Dict,
        record_data: Dict,
        correlations: List[Dict],
        discrepancies: List[Dict]
    ) -> float:
        """Calculate confidence in synthesis"""
        base_confidence = 0.6
        
        # Increase confidence if we have both sources
        if image_findings and record_data:
            base_confidence += 0.15
        
        # Increase confidence for correlations
        if correlations:
            base_confidence += 0.1 * min(len(correlations), 2)
        
        # Decrease confidence for discrepancies
        if discrepancies:
            base_confidence -= 0.1 * len(discrepancies)
        
        return max(0.3, min(base_confidence, 0.9))
