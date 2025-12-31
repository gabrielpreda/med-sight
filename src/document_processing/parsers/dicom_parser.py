"""DICOM parser for medical images"""

from typing import Optional, Dict
import logging
from pathlib import Path
from datetime import datetime

try:
    import pydicom
    DICOM_AVAILABLE = True
except ImportError:
    DICOM_AVAILABLE = False
    logging.warning("pydicom not installed. DICOM parsing will not be available.")

from ...models.medical_image import MedicalImage, ImageType, ImageModality, MedicalImageMetadata


class DICOMParser:
    """Parser for DICOM medical images"""
    
    def __init__(self):
        """Initialize DICOM parser"""
        self.logger = logging.getLogger(__name__)
        
        if not DICOM_AVAILABLE:
            self.logger.error("pydicom not available. Install with: pip install pydicom")
    
    def parse(self, file_path: str, image_id: Optional[str] = None) -> Optional[MedicalImage]:
        """
        Parse DICOM file.
        
        Args:
            file_path: Path to DICOM file
            image_id: Optional image identifier
        
        Returns:
            MedicalImage or None if parsing fails
        """
        if not DICOM_AVAILABLE:
            self.logger.error("Cannot parse DICOM - pydicom not installed")
            return None
        
        try:
            path = Path(file_path)
            
            if not path.exists():
                self.logger.error(f"File not found: {file_path}")
                return None
            
            # Read DICOM file
            dcm = pydicom.dcmread(file_path)
            
            # Extract metadata
            metadata = self._extract_metadata(dcm)
            
            # Determine image type
            image_type = self._determine_image_type(dcm)
            
            # Create medical image
            # Note: For simplicity, we're storing the file path rather than converting to base64
            # In production, you might want to convert the pixel data to a standard image format
            
            medical_image = MedicalImage(
                image_id=image_id or path.stem,
                image_type=image_type,
                file_path=file_path,
                width=int(dcm.Columns) if hasattr(dcm, 'Columns') else None,
                height=int(dcm.Rows) if hasattr(dcm, 'Rows') else None,
                metadata=metadata
            )
            
            self.logger.info(f"Successfully parsed DICOM: {file_path}")
            return medical_image
            
        except Exception as e:
            self.logger.error(f"Failed to parse DICOM: {e}")
            return None
    
    def _extract_metadata(self, dcm) -> MedicalImageMetadata:
        """Extract metadata from DICOM"""
        metadata = MedicalImageMetadata()
        
        # Patient ID
        if hasattr(dcm, 'PatientID'):
            metadata.patient_id = str(dcm.PatientID)
        
        # Study date
        if hasattr(dcm, 'StudyDate'):
            try:
                date_str = str(dcm.StudyDate)
                metadata.study_date = datetime.strptime(date_str, '%Y%m%d')
            except:
                pass
        
        # Modality
        if hasattr(dcm, 'Modality'):
            modality_map = {
                'CT': ImageModality.COMPUTED_TOMOGRAPHY,
                'MR': ImageModality.MAGNETIC_RESONANCE,
                'US': ImageModality.ULTRASOUND,
                'CR': ImageModality.RADIOGRAPHY,
                'DX': ImageModality.RADIOGRAPHY,
                'NM': ImageModality.NUCLEAR_MEDICINE,
            }
            metadata.modality = modality_map.get(str(dcm.Modality), ImageModality.OTHER)
        
        # Body part
        if hasattr(dcm, 'BodyPartExamined'):
            metadata.body_part = str(dcm.BodyPartExamined)
        
        # Institution
        if hasattr(dcm, 'InstitutionName'):
            metadata.institution = str(dcm.InstitutionName)
        
        # Study description
        if hasattr(dcm, 'StudyDescription'):
            metadata.study_description = str(dcm.StudyDescription)
        
        # Series description
        if hasattr(dcm, 'SeriesDescription'):
            metadata.series_description = str(dcm.SeriesDescription)
        
        return metadata
    
    def _determine_image_type(self, dcm) -> ImageType:
        """Determine image type from DICOM"""
        if hasattr(dcm, 'Modality'):
            modality = str(dcm.Modality).upper()
            
            if modality in ['CR', 'DX']:
                return ImageType.XRAY
            elif modality == 'CT':
                return ImageType.CT
            elif modality == 'MR':
                return ImageType.MRI
            elif modality == 'US':
                return ImageType.ULTRASOUND
            elif modality in ['PT', 'NM']:
                return ImageType.PET
        
        return ImageType.UNKNOWN
