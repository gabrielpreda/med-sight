"""Output validation and disclaimer management"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional
import logging
import re


class OutputValidator:
    """Validates and enhances model outputs for medical safety"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize output validator.
        
        Args:
            config_path: Path to guardrails configuration file
        """
        self.logger = logging.getLogger(__name__)
        
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "guardrails.yaml"
        
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.warning(f"Config file not found: {config_path}. Using defaults.")
            self.config = self._get_default_config()
        
        self.output_config = self.config.get('output_validation', {})
        self.disclaimers = self.config.get('disclaimers', {})
    
    def _get_default_config(self) -> Dict:
        """Get default configuration"""
        return {
            'output_validation': {
                'prohibited_output_phrases': ['definitely', 'certainly', '100% sure'],
                'confidence_thresholds': {'high': 0.85, 'medium': 0.65, 'low': 0.45}
            },
            'disclaimers': {
                'general': '⚕️ MEDICAL DISCLAIMER: This analysis is for informational purposes only.',
                'diagnostic': '⚕️ DIAGNOSTIC DISCLAIMER: These are preliminary findings.',
                'emergency': '🚨 EMERGENCY: If experiencing a medical emergency, call 911.',
                'limitation': '⚠️ LIMITATIONS: AI analysis has inherent limitations.'
            }
        }
    
    def validate_output(self, output: str, confidence: float = 1.0) -> Dict:
        """
        Validate model output for safety.
        
        Args:
            output: Model output text
            confidence: Confidence score
        
        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []
        
        # Check for prohibited phrases
        prohibited_phrases = self.output_config.get('prohibited_output_phrases', [])
        for phrase in prohibited_phrases:
            if phrase.lower() in output.lower():
                issues.append(f"Output contains prohibited phrase: '{phrase}'")
        
        # Check confidence level
        thresholds = self.output_config.get('confidence_thresholds', {})
        if confidence < thresholds.get('low', 0.45):
            warnings.append("Very low confidence - human review strongly recommended")
        elif confidence < thresholds.get('medium', 0.65):
            warnings.append("Low confidence - human review recommended")
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'confidence_level': self._get_confidence_level(confidence),
            'requires_human_review': confidence < thresholds.get('medium', 0.65)
        }
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Get confidence level label"""
        thresholds = self.output_config.get('confidence_thresholds', {})
        
        if confidence >= thresholds.get('high', 0.85):
            return 'high'
        elif confidence >= thresholds.get('medium', 0.65):
            return 'medium'
        else:
            return 'low'
    
    def add_disclaimer(
        self,
        output: str,
        disclaimer_type: str = 'general',
        is_emergency: bool = False,
        confidence: float = 1.0
    ) -> str:
        """
        Add appropriate medical disclaimer to output.
        
        Args:
            output: Original output text
            disclaimer_type: Type of disclaimer ('general', 'diagnostic', 'treatment', etc.)
            is_emergency: Whether this is an emergency situation
            confidence: Confidence score
        
        Returns:
            Output with disclaimer prepended
        """
        disclaimers_to_add = []
        
        # Emergency disclaimer takes precedence
        if is_emergency:
            emergency_disclaimer = self.disclaimers.get('emergency', '')
            if emergency_disclaimer:
                disclaimers_to_add.append(emergency_disclaimer)
                disclaimers_to_add.append("")  # Empty line
        
        # Add primary disclaimer
        primary_disclaimer = self.disclaimers.get(disclaimer_type, self.disclaimers.get('general', ''))
        if primary_disclaimer:
            disclaimers_to_add.append(primary_disclaimer)
            disclaimers_to_add.append("")
        
        # Add limitation disclaimer for low confidence
        thresholds = self.output_config.get('confidence_thresholds', {})
        if confidence < thresholds.get('medium', 0.65):
            limitation_disclaimer = self.disclaimers.get('limitation', '')
            if limitation_disclaimer:
                disclaimers_to_add.append(limitation_disclaimer)
                disclaimers_to_add.append("")
        
        # Combine disclaimers with output
        if disclaimers_to_add:
            disclaimer_text = '\n'.join(disclaimers_to_add)
            return f"{disclaimer_text}\n{output}"
        
        return output
    
    def add_confidence_indicator(self, output: str, confidence: float) -> str:
        """
        Add confidence indicator to output.
        
        Args:
            output: Original output
            confidence: Confidence score
        
        Returns:
            Output with confidence indicator
        """
        confidence_level = self._get_confidence_level(confidence)
        
        indicators = {
            'high': '🟢',
            'medium': '🟡',
            'low': '🔴'
        }
        
        indicator = indicators.get(confidence_level, '⚪')
        confidence_text = f"\n\n{indicator} **Confidence Level**: {confidence_level.upper()} ({confidence:.2%})"
        
        return output + confidence_text
    
    def format_medical_output(
        self,
        output: str,
        confidence: float = 1.0,
        disclaimer_type: str = 'diagnostic',
        is_emergency: bool = False,
        add_confidence: bool = True
    ) -> str:
        """
        Format medical output with all safety enhancements.
        
        Args:
            output: Original output
            confidence: Confidence score
            disclaimer_type: Type of disclaimer
            is_emergency: Emergency flag
            add_confidence: Whether to add confidence indicator
        
        Returns:
            Fully formatted output
        """
        # Add disclaimer
        formatted = self.add_disclaimer(output, disclaimer_type, is_emergency, confidence)
        
        # Add confidence indicator
        if add_confidence:
            formatted = self.add_confidence_indicator(formatted, confidence)
        
        return formatted
