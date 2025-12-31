"""Text parser for medical notes"""

from typing import Optional
import logging
from pathlib import Path

from ...models.medical_record import MedicalRecord, RecordType, DocumentFormat


class TextParser:
    """Parser for text-based medical records"""
    
    def __init__(self):
        """Initialize text parser"""
        self.logger = logging.getLogger(__name__)
    
    def parse(self, file_path: str, record_id: Optional[str] = None) -> Optional[MedicalRecord]:
        """
        Parse text file.
        
        Args:
            file_path: Path to text file
            record_id: Optional record identifier
        
        Returns:
            MedicalRecord or None if parsing fails
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                self.logger.error(f"File not found: {file_path}")
                return None
            
            # Read text content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content:
                self.logger.warning(f"Empty file: {file_path}")
                return None
            
            # Determine record type from content
            record_type = self._infer_record_type(content)
            
            # Create medical record
            record = MedicalRecord(
                record_id=record_id or path.stem,
                record_type=record_type,
                document_format=DocumentFormat.TEXT,
                content=content,
                file_path=file_path
            )
            
            self.logger.info(f"Successfully parsed text file: {file_path}")
            return record
            
        except Exception as e:
            self.logger.error(f"Failed to parse text file: {e}")
            return None
    
    def _infer_record_type(self, content: str) -> RecordType:
        """Infer record type from content"""
        content_lower = content.lower()
        
        if 'visit note' in content_lower or 'office visit' in content_lower:
            return RecordType.VISIT_NOTE
        elif 'progress note' in content_lower:
            return RecordType.PROGRESS_NOTE
        elif 'discharge' in content_lower:
            return RecordType.DISCHARGE_SUMMARY
        elif 'lab result' in content_lower or 'laboratory' in content_lower:
            return RecordType.LAB_RESULT
        elif 'radiology' in content_lower or 'imaging' in content_lower:
            return RecordType.RADIOLOGY_REPORT
        elif 'pathology' in content_lower:
            return RecordType.PATHOLOGY_REPORT
        else:
            return RecordType.CLINICAL_NOTE
