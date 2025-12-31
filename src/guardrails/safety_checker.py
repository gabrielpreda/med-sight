"""Safety checker for medical content"""

import logging
from typing import Dict, List, Optional
import yaml
from pathlib import Path


class SafetyChecker:
    """Checks medical content for safety concerns"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize safety checker"""
        self.logger = logging.getLogger(__name__)
        
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "guardrails.yaml"
        
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
            self.logger.warning(f"Config file not found: {config_path}")
            self.config = {}
        
        self.safety_config = self.config.get('safety_checks', {})
    
    def check_critical_findings(self, findings: str) -> Dict:
        """
        Check for critical medical findings that require immediate attention.
        
        Args:
            findings: Medical findings text
        
        Returns:
            Dictionary with safety check results
        """
        critical_findings = self.safety_config.get('critical_findings', [])
        detected_critical = []
        
        for critical_term in critical_findings:
            if critical_term.lower() in findings.lower():
                detected_critical.append(critical_term)
                self.logger.warning(f"Critical finding detected: {critical_term}")
        
        return {
            'has_critical_findings': len(detected_critical) > 0,
            'critical_findings': detected_critical,
            'requires_immediate_attention': len(detected_critical) > 0,
            'escalation_required': len(detected_critical) > 0
        }
    
    def requires_human_review(
        self,
        confidence: float,
        is_emergency: bool = False,
        has_critical_findings: bool = False,
        has_contradictions: bool = False
    ) -> Dict:
        """
        Determine if human review is required.
        
        Args:
            confidence: Confidence score
            is_emergency: Emergency flag
            has_critical_findings: Critical findings flag
            has_contradictions: Contradictory information flag
        
        Returns:
            Dictionary with review requirements
        """
        review_config = self.safety_config.get('human_review_required', {})
        
        # Handle both dict and list formats (for backward compatibility)
        if isinstance(review_config, list):
            # Old format: list of dicts - convert to single dict
            self.logger.warning("human_review_required is in old list format, converting to dict")
            temp_config = {}
            for item in review_config:
                if isinstance(item, dict):
                    temp_config.update(item)
            review_config = temp_config
        elif not isinstance(review_config, dict):
            # Invalid format - use defaults
            self.logger.error(f"Invalid human_review_required format: {type(review_config)}")
            review_config = {}
        
        confidence_threshold = review_config.get('confidence_below', 0.65)
        
        reasons = []
        
        if confidence < confidence_threshold:
            reasons.append(f"Low confidence ({confidence:.2%})")
        
        if is_emergency:
            reasons.append("Emergency situation detected")
        
        if has_critical_findings:
            reasons.append("Critical findings detected")
        
        if has_contradictions:
            reasons.append("Contradictory information found")
        
        return {
            'requires_review': len(reasons) > 0,
            'reasons': reasons,
            'priority': self._get_review_priority(is_emergency, has_critical_findings, confidence)
        }
    
    def _get_review_priority(
        self,
        is_emergency: bool,
        has_critical_findings: bool,
        confidence: float
    ) -> str:
        """Get review priority level"""
        if is_emergency or has_critical_findings:
            return 'urgent'
        elif confidence < 0.5:
            return 'high'
        elif confidence < 0.65:
            return 'medium'
        else:
            return 'low'
    
    def check_safety(
        self,
        output: str,
        confidence: float,
        is_emergency: bool = False
    ) -> Dict:
        """
        Comprehensive safety check.
        
        Args:
            output: Model output
            confidence: Confidence score
            is_emergency: Emergency flag
        
        Returns:
            Comprehensive safety check results
        """
        # Check for critical findings
        critical_check = self.check_critical_findings(output)
        
        # Check if human review required
        review_check = self.requires_human_review(
            confidence=confidence,
            is_emergency=is_emergency,
            has_critical_findings=critical_check['has_critical_findings']
        )
        
        return {
            'safe_to_display': not (is_emergency and critical_check['has_critical_findings']),
            'critical_findings': critical_check,
            'human_review': review_check,
            'is_emergency': is_emergency,
            'confidence': confidence
        }
