"""Record Parser Agent for extracting information from medical documents"""

from typing import Any, Dict, List, Optional
import re
import logging
import json
import vertexai
from vertexai.generative_models import GenerativeModel

from .base_agent import BaseAgent, AgentType, AgentResult
from ..models.medical_record import MedicalRecord, MedicalEntity


class RecordParserAgent(BaseAgent):
    """
    Agent specialized in parsing medical records and extracting structured information.
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize record parser agent"""
        super().__init__(
            agent_type=AgentType.RECORD_PARSER,
            name="RecordParserAgent",
            config=config
        )
        
        # Initialize Gemini Model
        self.model_name = "gemini-2.5-flash-lite" # Fast and capable
        try:
            self.model = GenerativeModel(self.model_name)
            self.logger.info(f"Initialized underlying model: {self.model_name}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Gemini model: {e}")
            self.model = None
        
        # Common medical patterns
        self.patterns = {
            'diagnosis': r'(?:diagnosis|diagnosed with|impression):\s*([^\n]+)',
            'medication': r'(?:medication|prescribed|rx):\s*([^\n]+)',
            'procedure': r'(?:procedure|surgery|operation):\s*([^\n]+)',
            'date': r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        }
    
    def validate_input(self, input_data: Any) -> bool:
        """Validate input"""
        if isinstance(input_data, MedicalRecord):
            return True
        if isinstance(input_data, dict) and 'content' in input_data:
            return True
        return False
    
    async def process(self, input_data: Any, context: Optional[Dict] = None) -> AgentResult:
        """
        Parse medical record using Regex + Gemini.
        
        Args:
            input_data: MedicalRecord or dict with 'content'
            context: Optional context
        
        Returns:
            AgentResult with extracted information
        """
        try:
            self.logger.info(f"Processing input data: {input_data}")
            # Extract content
            if isinstance(input_data, MedicalRecord):
                record = input_data
                content = record.content
            else:
                content = input_data.get('content', '')
                record = None
            
            # 1. Regex Extraction (Fast, explicit)
            entities = self._extract_entities(content)
            regex_diagnoses = self._extract_diagnoses(content)
            regex_medications = self._extract_medications(content)
            regex_procedures = self._extract_procedures(content)
            dates = self._extract_dates(content)
            
            self.logger.info(f"Regex found: {len(regex_diagnoses)} diagnoses, {len(regex_medications)} meds")
            
            # 2. Gemini Analysis (Deep interpretation)
            llm_data = await self._analyze_with_gemini(content)
            
            # 3. Merge Results (LLM usually better for narrative, Regex good for dates/specifics)
            
            # Combine unique entries, preferring LLM for structured lists usually
            merged_diagnoses = list(set(regex_diagnoses + llm_data.get('diagnoses', [])))
            merged_medications = list(set(regex_medications + llm_data.get('medications', [])))
            merged_procedures = list(set(regex_procedures + llm_data.get('procedures', [])))
            
            # Parse entities from LLM if provided
            if 'entities' in llm_data and isinstance(llm_data['entities'], list):
               # Convert LLM entities to simple dicts if needed or just use text
               pass

            # Build structured output
            parsed_data = {
                'entities': [e.dict() for e in entities], # Keep regex entities (dates, etc)
                'diagnoses': merged_diagnoses,
                'medications': merged_medications,
                'procedures': merged_procedures,
                'dates': dates, # Regex is usually best for dates
                'summary': llm_data.get('summary', self._generate_summary(merged_diagnoses, merged_medications, merged_procedures)),
                'analysis_notes': llm_data.get('analysis_notes', '')
            }
            
            # Calculate confidence 
            confidence = self._calculate_confidence(parsed_data)
            
            # Logic: If LLM worked well, boost confidence
            if llm_data.get('success', False):
                confidence = max(confidence, 0.85)

            return AgentResult(
                success=True,
                data=parsed_data,
                confidence=confidence,
                metadata={
                    'content_length': len(content),
                    'regex_entities': len(entities),
                    'llm_used': llm_data.get('success', False)
                },
                sources=['Regex Parser', self.model_name]
            )
            
        except Exception as e:
            self.logger.error(f"Record parsing failed: {e}")
            return AgentResult(
                success=False,
                data=None,
                error=str(e)
            )

    async def _analyze_with_gemini(self, text: str) -> Dict:
        """Call Gemini to interpret the medical report"""
        if not self.model:
            return {'success': False}
            
        prompt = f"""
        You are an expert medical AI assistant. Analyze the following medical record/report and extract structured information.
        
        TEXT:
        {text[:10000]}  # Truncate if too long to avoid token limits
        
        INSTRUCTIONS:
        1. Extract a clear list of CONFIRMED diagnoses. Ignore "rule out" or "suspected" unless stated otherwise.
        2. Extract a list of CURRENT medications.
        3. Extract any procedures performed or scheduled.
        4. Provide a professional summary of the key findings (2-3 sentences).
        5. Identify any critical red flags.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "diagnoses": ["list", "of", "strings"],
            "medications": ["list", "of", "strings"],
            "procedures": ["list", "of", "strings"],
            "summary": "Professional summary...",
            "critical_flags": ["list of flags"],
            "analysis_notes": "Any other relevant observations"
        }}
        """
        
        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            if response.text:
                data = json.loads(response.text)
                data['success'] = True
                self.logger.info("Gemini analysis successful")
                return data
            else:
                self.logger.warning("Empty response from Gemini")
                return {'success': False}
                
        except Exception as e:
            self.logger.error(f"Gemini analysis failed: {e}")
            return {'success': False}
    
    def _extract_entities(self, content: str) -> List[MedicalEntity]:
        """Extract medical entities from text"""
        entities = []
        
        # Extract using patterns
        for entity_type, pattern in self.patterns.items():
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                entities.append(MedicalEntity(
                    entity_type=entity_type,
                    text=match.group(1).strip(),
                    confidence=0.7,
                    start_pos=match.start(),
                    end_pos=match.end()
                ))
        
        return entities

    def _extract_diagnoses(self, content: str) -> List[str]:
        """Extract diagnoses from text using multiple strategies"""
        diagnoses = []
        
        # Strategy 1: Explicit headers (Strict: require colon)
        # Matches "Diagnosis: Pneumonia"
        header_patterns = [
            r'(?:diagnosis|impression|assessment):\s*([^\n\.]+)',
            r'diagnosed with\s+([^\n\.]+)'
        ]
        
        for p in header_patterns:
            matches = re.finditer(p, content, re.IGNORECASE)
            for match in matches:
                val = match.group(1).strip()
                if self._is_valid_medical_text(val):
                    diagnoses.append(val)
                
        # Strategy 2: Narrative phrases
        # "history of X", "found to have X", "suffers from X"
        narrative_patterns = [
            r'\bhistory of\s+([a-z\s]+)(?:,|\.|and)',
            r'\bdiagnosed with\s+([a-z\s]+)(?:,|\.|and)',
            r'\bfound to have\s+([a-z\s]+)(?:,|\.|and)',
            r'\bsuffers from\s+([a-z\s]+)(?:,|\.|and)'
        ]
        
        for pattern in narrative_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                val = match.group(1).strip()
                if self._is_valid_medical_text(val):
                     diagnoses.append(val)

        return list(set(diagnoses)) # Deduplicate
    
    def _extract_medications(self, content: str) -> List[str]:
        """Extract medications"""
        medications = []
        
        # Strategy 1: Headers (Strict: require colon)
        match = re.search(r'(?:medication|medications|prescribed|rx|treatment):\s*([^\n\.]+)', content, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            # Split comma separated lists
            for item in val.split(','):
                clean_item = item.strip()
                if self._is_valid_medical_text(clean_item): 
                    medications.append(clean_item)

        # Strategy 2: Narrative "started on X", "taking X"
        narrative_patterns = [
            r'\bstarted on\s+([a-z\s]+)(?:,|\.|and)',
            r'\bprescribed\s+([a-z\s]+)(?:,|\.|and)',
            r'\btaking\s+([a-z\s]+)(?:,|\.|and)'
        ]
        for pattern in narrative_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                val = match.group(1).strip()
                if self._is_valid_medical_text(val, max_words=3):
                    medications.append(val)
                    
        return list(set(medications))
    
    def _extract_procedures(self, content: str) -> List[str]:
        """Extract procedures"""
        procedures = []
        
        # Strategy 1: Headers (Strict: require colon)
        match = re.search(r'(?:procedure|procedures|surgery|operation|plan):\s*([^\n\.]+)', content, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            if self._is_valid_medical_text(val):
                procedures.append(val)
        
        # Strategy 2: Narrative
        narrative_patterns = [
            r'\bunderwent\s+([a-z\s]+)(?:,|\.|and)',
            r'\bscheduled for\s+([a-z\s]+)(?:,|\.|and)',
            r'\bperformed\s+(?!by\b)([a-z\s]+)(?:,|\.|and)' # Negative lookahead for "by"
        ]
        for pattern in narrative_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                val = match.group(1).strip()
                if self._is_valid_medical_text(val):
                    procedures.append(val)

        return list(set(procedures))

    def _is_valid_medical_text(self, text: str, max_words: int = 15) -> bool:
        """Check if extracted text looks like valid medical text"""
        if not text or len(text) < 3 or len(text) > 100:
            return False
            
        # Check word count
        words = text.split()
        if len(words) > max_words:
            return False
            
        # Common false positives
        invalid_starts = ['by', 'the', 'a', 'in', 'on', 'at', 'to', 'list', 'summary', 'note']
        if words[0].lower() in invalid_starts:
            return False
            
        # Specific invalid phrases
        invalid_phrases = [
            'several different physicians',
            'quite different circumstances',
            'markedly reduced risk',
            'differential diagnosis list',
            'no known allergies',
            'review of systems'
        ]
        
        if text.lower() in invalid_phrases:
            return False
            
        return True

    def _extract_dates(self, content: str) -> List[str]:
        """Extract dates"""
        dates = []
        pattern = self.patterns['date']
        matches = re.finditer(pattern, content)
        
        for match in matches:
            dates.append(match.group(1))
        
        return list(set(dates))  # Remove duplicates
    
    def _generate_summary(
        self,
        diagnoses: List[str],
        medications: List[str],
        procedures: List[str]
    ) -> str:
        """Generate a summary of extracted information"""
        summary_parts = []
        
        if diagnoses:
            summary_parts.append(f"Diagnoses: {', '.join(diagnoses[:5])}")
        if medications:
            summary_parts.append(f"Medications: {', '.join(medications[:5])}")
        if procedures:
            summary_parts.append(f"Procedures: {', '.join(procedures[:5])}")
        
        if not summary_parts:
            return "No structured information extracted."
        
        return " | ".join(summary_parts)
    
    def _calculate_confidence(self, parsed_data: Dict) -> float:
        """Calculate confidence score based on extraction results"""
        base_confidence = 0.5
        
        # Increase confidence based on what was found
        # Weighted simple mechanism
        score = 0
        if parsed_data['diagnoses']: score += 0.2
        if parsed_data['medications']: score += 0.2
        if parsed_data['procedures']: score += 0.1
        if len(parsed_data['dates']) > 0: score += 0.1
        
        # If we found at least something, confidence is better than 0.5
        if score > 0:
            return min(base_confidence + score, 0.95)
        
        return 0.4  # Low confidence if nothing found
