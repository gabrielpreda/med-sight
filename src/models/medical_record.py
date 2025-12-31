"""Medical record data models"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class RecordType(str, Enum):
    """Medical record type enumeration"""
    CLINICAL_NOTE = "clinical_note"
    LAB_RESULT = "lab_result"
    RADIOLOGY_REPORT = "radiology_report"
    PATHOLOGY_REPORT = "pathology_report"
    DISCHARGE_SUMMARY = "discharge_summary"
    PRESCRIPTION = "prescription"
    VISIT_NOTE = "visit_note"
    PROGRESS_NOTE = "progress_note"
    OTHER = "other"


class DocumentFormat(str, Enum):
    """Document format enumeration"""
    PDF = "pdf"
    TEXT = "text"
    DOCX = "docx"
    HL7 = "hl7"
    FHIR = "fhir"
    JSON = "json"
    XML = "xml"
    DICOM = "dicom"


class MedicalEntity(BaseModel):
    """Extracted medical entity"""
    
    entity_type: str  # e.g., "diagnosis", "medication", "procedure"
    text: str
    code: Optional[str] = None  # ICD, CPT, RxNorm, etc.
    code_system: Optional[str] = None
    confidence: float = 1.0
    start_pos: Optional[int] = None
    end_pos: Optional[int] = None


class MedicalRecord(BaseModel):
    """Medical record data model"""
    
    record_id: str
    record_type: RecordType
    document_format: DocumentFormat
    content: str  # Raw text content
    file_path: Optional[str] = None
    patient_id: Optional[str] = None
    record_date: Optional[datetime] = None
    author: Optional[str] = None
    institution: Optional[str] = None
    
    # Extracted information
    entities: List[MedicalEntity] = Field(default_factory=list)
    diagnoses: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)
    procedures: List[str] = Field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    processed: bool = False
    
    class Config:
        use_enum_values = True


class PatientTimeline(BaseModel):
    """Patient medical timeline"""
    
    patient_id: str
    events: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def add_event(self, event_date: datetime, event_type: str, description: str, source: str):
        """Add an event to the timeline"""
        self.events.append({
            "date": event_date,
            "type": event_type,
            "description": description,
            "source": source
        })
        self.events.sort(key=lambda x: x["date"])
        self.updated_at = datetime.utcnow()
    
    def get_events_in_range(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get events within a date range"""
        return [
            event for event in self.events
            if start_date <= event["date"] <= end_date
        ]
