"""Medical image data models"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import base64
from io import BytesIO
from PIL import Image


class ImageType(str, Enum):
    """Medical image type enumeration"""
    XRAY = "xray"
    MRI = "mri"
    CT = "ct"
    ULTRASOUND = "ultrasound"
    MAMMOGRAM = "mammogram"
    PET = "pet"
    HISTOPATHOLOGY = "histopathology"
    DERMATOLOGY = "dermatology"
    UNKNOWN = "unknown"


class ImageModality(str, Enum):
    """Imaging modality"""
    RADIOGRAPHY = "radiography"
    COMPUTED_TOMOGRAPHY = "computed_tomography"
    MAGNETIC_RESONANCE = "magnetic_resonance"
    ULTRASOUND = "ultrasound"
    NUCLEAR_MEDICINE = "nuclear_medicine"
    OTHER = "other"


class MedicalImageMetadata(BaseModel):
    """Metadata for medical images"""
    
    patient_id: Optional[str] = None
    study_date: Optional[datetime] = None
    modality: Optional[ImageModality] = None
    body_part: Optional[str] = None
    view_position: Optional[str] = None
    institution: Optional[str] = None
    referring_physician: Optional[str] = None
    study_description: Optional[str] = None
    series_description: Optional[str] = None
    additional_info: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class MedicalImage(BaseModel):
    """Medical image data model"""
    
    image_id: str
    image_type: ImageType = ImageType.UNKNOWN
    image_data: Optional[str] = None  # Base64 encoded
    file_path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    metadata: MedicalImageMetadata = Field(default_factory=MedicalImageMetadata)
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)
    quality_score: Optional[float] = None
    
    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True
    
    @classmethod
    def from_pil_image(cls, image: Image.Image, image_id: str, image_type: ImageType = ImageType.UNKNOWN):
        """Create MedicalImage from PIL Image"""
        # Encode image to base64
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        
        return cls(
            image_id=image_id,
            image_type=image_type,
            image_data=img_b64,
            width=image.size[0],
            height=image.size[1]
        )
    
    def get_data_url(self) -> str:
        """Get data URL for the image"""
        if self.image_data:
            return f"data:image/png;base64,{self.image_data}"
        return ""
    
    def to_pil_image(self) -> Optional[Image.Image]:
        """Convert to PIL Image"""
        if self.image_data:
            img_bytes = base64.b64decode(self.image_data)
            return Image.open(BytesIO(img_bytes))
        return None
