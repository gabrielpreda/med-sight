"""Compliance checker for healthcare regulations"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
import hashlib


class ComplianceChecker:
    """Ensures compliance with healthcare regulations (HIPAA, etc.)"""
    
    def __init__(self):
        """Initialize compliance checker"""
        self.logger = logging.getLogger(__name__)
        self.audit_log = []
    
    def log_interaction(
        self,
        session_id: str,
        user_id: Optional[str],
        action: str,
        data_accessed: List[str],
        result: str
    ) -> Dict:
        """
        Log interaction for audit trail.
        
        Args:
            session_id: Session identifier
            user_id: User identifier (hashed)
            action: Action performed
            data_accessed: List of data types accessed
            result: Result of action
        
        Returns:
            Audit log entry
        """
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'session_id': session_id,
            'user_id': self._hash_identifier(user_id) if user_id else None,
            'action': action,
            'data_accessed': data_accessed,
            'result': result
        }
        
        self.audit_log.append(entry)
        self.logger.info(f"Audit log entry created: {action}")
        
        return entry
    
    def _hash_identifier(self, identifier: str) -> str:
        """Hash identifier for privacy"""
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]
    
    def check_data_retention(self, data_age_days: int) -> Dict:
        """
        Check if data should be retained or deleted.
        
        Args:
            data_age_days: Age of data in days
        
        Returns:
            Retention policy result
        """
        # Default retention periods
        conversation_retention = 90  # days
        audit_log_retention = 2555  # 7 years
        
        return {
            'should_retain_conversation': data_age_days < conversation_retention,
            'should_retain_audit_log': data_age_days < audit_log_retention,
            'action_required': data_age_days >= conversation_retention
        }
    
    def anonymize_data(self, data: Dict) -> Dict:
        """
        Anonymize patient data for logging.
        
        Args:
            data: Original data
        
        Returns:
            Anonymized data
        """
        anonymized = data.copy()
        
        # Remove or hash sensitive fields
        sensitive_fields = ['patient_id', 'user_id', 'name', 'email', 'phone']
        
        for field in sensitive_fields:
            if field in anonymized:
                if anonymized[field]:
                    anonymized[field] = self._hash_identifier(str(anonymized[field]))
        
        return anonymized
    
    def get_audit_log(self, session_id: Optional[str] = None) -> List[Dict]:
        """
        Get audit log entries.
        
        Args:
            session_id: Optional session filter
        
        Returns:
            List of audit log entries
        """
        if session_id:
            return [entry for entry in self.audit_log if entry['session_id'] == session_id]
        return self.audit_log
