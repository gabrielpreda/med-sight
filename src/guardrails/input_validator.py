"""Input validation for healthcare safety"""

import re
from typing import Dict, List, Optional, Tuple
import yaml
from pathlib import Path
import logging


class ValidationResult:
    """Result of input validation"""
    
    def __init__(
        self,
        valid: bool,
        issues: List[str] = None,
        is_emergency: bool = False,
        pii_detected: bool = False,
        pii_types: List[str] = None,
        warnings: List[str] = None
    ):
        self.valid = valid
        self.issues = issues or []
        self.is_emergency = is_emergency
        self.pii_detected = pii_detected
        self.pii_types = pii_types or []
        self.warnings = warnings or []
    
    def to_dict(self) -> Dict:
        return {
            "valid": self.valid,
            "issues": self.issues,
            "is_emergency": self.is_emergency,
            "pii_detected": self.pii_detected,
            "pii_types": self.pii_types,
            "warnings": self.warnings
        }


class InputValidator:
    """Validates user input for safety and compliance"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize input validator.
        
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
        
        self.input_config = self.config.get('input_validation', {})
    
    def _get_default_config(self) -> Dict:
        """Get default configuration if file not found"""
        return {
            'input_validation': {
                'max_query_length': 2000,
                'min_query_length': 3,
                'blocked_patterns': ['prescribe', 'dosage for'],
                'emergency_keywords': ['chest pain', 'difficulty breathing', 'severe bleeding'],
                'pii_patterns': []
            }
        }
    
    def validate_query(self, query: str) -> ValidationResult:
        """
        Validate user query.
        
        Args:
            query: User's text query
        
        Returns:
            ValidationResult object
        """
        issues = []
        warnings = []
        
        # Check length
        min_length = self.input_config.get('min_query_length', 3)
        max_length = self.input_config.get('max_query_length', 2000)
        
        if len(query) < min_length:
            issues.append(f"Query too short (minimum {min_length} characters)")
        
        if len(query) > max_length:
            issues.append(f"Query too long (maximum {max_length} characters)")
        
        # Check for blocked patterns
        blocked_patterns = self.input_config.get('blocked_patterns', [])
        for pattern in blocked_patterns:
            if pattern.lower() in query.lower():
                issues.append(f"Query contains blocked content: '{pattern}'")
                warnings.append(
                    "This system cannot provide medical prescriptions or treatment recommendations. "
                    "Please consult with a healthcare professional."
                )
        
        # Check for emergency keywords
        is_emergency = self._detect_emergency(query)
        
        # Check for PII
        pii_detected, pii_types = self._detect_pii(query)
        if pii_detected:
            warnings.append(
                "Potential personally identifiable information detected. "
                "Please avoid sharing sensitive personal information."
            )
        
        return ValidationResult(
            valid=len(issues) == 0,
            issues=issues,
            is_emergency=is_emergency,
            pii_detected=pii_detected,
            pii_types=pii_types,
            warnings=warnings
        )
    
    def _detect_emergency(self, text: str) -> bool:
        """Detect emergency situations"""
        emergency_keywords = self.input_config.get('emergency_keywords', [])
        
        for keyword in emergency_keywords:
            if keyword.lower() in text.lower():
                self.logger.warning(f"Emergency keyword detected: {keyword}")
                return True
        
        return False
    
    def _detect_pii(self, text: str) -> Tuple[bool, List[str]]:
        """
        Detect personally identifiable information.
        
        Returns:
            Tuple of (pii_detected, list of pii types)
        """
        pii_types = []
        pii_patterns = self.input_config.get('pii_patterns', [])
        
        for pattern_config in pii_patterns:
            pattern = pattern_config.get('regex', '')
            pii_type = pattern_config.get('type', 'unknown')
            
            if re.search(pattern, text):
                pii_types.append(pii_type)
                self.logger.warning(f"PII detected: {pii_type}")
        
        return len(pii_types) > 0, pii_types
    
    def sanitize_query(self, query: str) -> str:
        """
        Sanitize query by removing or masking PII.
        
        Args:
            query: Original query
        
        Returns:
            Sanitized query
        """
        sanitized = query
        pii_patterns = self.input_config.get('pii_patterns', [])
        
        for pattern_config in pii_patterns:
            pattern = pattern_config.get('regex', '')
            pii_type = pattern_config.get('type', 'unknown')
            
            # Replace PII with masked version
            sanitized = re.sub(pattern, f'[{pii_type.upper()}_REDACTED]', sanitized)
        
        return sanitized
