"""PDF parser for medical records"""

from typing import Optional, Dict
import logging
from pathlib import Path

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("PyPDF2 not installed. PDF parsing will not be available.")

from ...models.medical_record import MedicalRecord, RecordType, DocumentFormat


class PDFParser:
    """Parser for PDF medical records"""
    
    def __init__(self):
        """Initialize PDF parser"""
        self.logger = logging.getLogger(__name__)
        
        if not PDF_AVAILABLE:
            self.logger.error("PyPDF2 not available. Install with: pip install PyPDF2")
    
    def parse(self, file_path: str, record_id: Optional[str] = None) -> Optional[MedicalRecord]:
        """
        Parse PDF file and extract text.
        
        Args:
            file_path: Path to PDF file
            record_id: Optional record identifier
        
        Returns:
            MedicalRecord or None if parsing fails
        """
        if not PDF_AVAILABLE:
            self.logger.error("Cannot parse PDF - PyPDF2 not installed")
            return None
        
        try:
            path = Path(file_path)
            
            if not path.exists():
                self.logger.error(f"File not found: {file_path}")
                return None
            
            # Extract text from PDF
            text = self._extract_text(file_path)
            
            if not text:
                self.logger.warning(f"No text extracted from {file_path}")
                return None
            
            # Create medical record
            record = MedicalRecord(
                record_id=record_id or path.stem,
                record_type=RecordType.OTHER,
                document_format=DocumentFormat.PDF,
                content=text,
                file_path=file_path
            )
            
            self.logger.info(f"Successfully parsed PDF: {file_path}")
            return record
            
        except Exception as e:
            self.logger.error(f"Failed to parse PDF: {e}")
            return None
    
    def _extract_text(self, file_path: str) -> str:
        """Extract text from PDF"""
        text_parts = []
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
            
            return "\n\n".join(text_parts)
            
        except Exception as e:
            self.logger.error(f"Text extraction failed: {e}")
            return ""
