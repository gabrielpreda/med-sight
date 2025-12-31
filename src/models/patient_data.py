"""Patient data aggregation models"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from .medical_image import MedicalImage
from .medical_record import MedicalRecord, PatientTimeline


class PatientData(BaseModel):
    """Aggregated patient data container"""
    
    patient_id: str
    images: List[MedicalImage] = Field(default_factory=list)
    records: List[MedicalRecord] = Field(default_factory=list)
    timeline: Optional[PatientTimeline] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
    
    def add_image(self, image: MedicalImage):
        """Add a medical image"""
        self.images.append(image)
        self.updated_at = datetime.utcnow()
    
    def add_record(self, record: MedicalRecord):
        """Add a medical record"""
        self.records.append(record)
        self.updated_at = datetime.utcnow()
    
    def get_images_by_type(self, image_type: str) -> List[MedicalImage]:
        """Get images of a specific type"""
        return [img for img in self.images if img.image_type == image_type]
    
    def get_records_by_type(self, record_type: str) -> List[MedicalRecord]:
        """Get records of a specific type"""
        return [rec for rec in self.records if rec.record_type == record_type]
    
    def get_recent_images(self, n: int = 5) -> List[MedicalImage]:
        """Get n most recent images"""
        sorted_images = sorted(self.images, key=lambda x: x.upload_timestamp, reverse=True)
        return sorted_images[:n]
    
    def get_recent_records(self, n: int = 5) -> List[MedicalRecord]:
        """Get n most recent records"""
        sorted_records = sorted(self.records, key=lambda x: x.upload_timestamp, reverse=True)
        return sorted_records[:n]


class AnalysisContext(BaseModel):
    """Context for medical analysis"""
    
    patient_data: Optional[PatientData] = None
    current_query: str
    conversation_history: List[Dict] = Field(default_factory=list)
    focus_areas: List[str] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
