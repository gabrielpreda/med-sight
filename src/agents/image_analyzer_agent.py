"""
Image Analyzer Agent for MedSight

This agent specializes in analyzing medical images using the MedGemma model.
It extracts findings, identifies abnormalities, and provides structured analysis.
"""

from typing import Any, Dict, List, Optional
import base64
from io import BytesIO
from PIL import Image
from google.cloud import aiplatform
import json
import re
from .base_agent import BaseAgent, AgentType, AgentResult


class MedicalImageData:
    """Container for medical image data"""
    
    def __init__(
        self,
        image: Image.Image,
        image_type: str = "unknown",
        metadata: Optional[Dict] = None
    ):
        self.image = image
        self.image_type = image_type  # e.g., "xray", "mri", "ct", "ultrasound"
        self.metadata = metadata or {}
        self.base64_data = self._encode_image()
    
    def _encode_image(self) -> str:
        """Encode image to base64 for API transmission"""
        buffered = BytesIO()
        self.image.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        return base64.b64encode(img_bytes).decode("utf-8")
    
    def get_data_url(self) -> str:
        """Get data URL for the image"""
        return f"data:image/png;base64,{self.base64_data}"


class ImageAnalysisResult:
    """Structured result from image analysis"""
    
    def __init__(
        self,
        summary: str,
        detailed_findings: List[Dict],
        anatomical_structures: List[str],
        abnormalities: List[Dict],
        image_quality: Dict,
        confidence: float,
        recommendations: List[str]
    ):
        self.summary = summary
        self.detailed_findings = detailed_findings
        self.anatomical_structures = anatomical_structures
        self.abnormalities = abnormalities
        self.image_quality = image_quality
        self.confidence = confidence
        self.recommendations = recommendations
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "summary": self.summary,
            "detailed_findings": self.detailed_findings,
            "anatomical_structures": self.anatomical_structures,
            "abnormalities": self.abnormalities,
            "image_quality": self.image_quality,
            "confidence": self.confidence,
            "recommendations": self.recommendations
        }


class ImageAnalyzerAgent(BaseAgent):
    """
    Agent specialized in medical image analysis.
    
    This agent:
    1. Validates image quality
    2. Analyzes images using MedGemma
    3. Extracts structured findings
    4. Identifies abnormalities
    5. Provides confidence scores
    """
    
    def __init__(
        self,
        endpoint: aiplatform.Endpoint,
        config: Optional[Dict] = None
    ):
        """
        Initialize the Image Analyzer Agent.
        
        Args:
            endpoint: Vertex AI endpoint for MedGemma model
            config: Optional configuration dictionary
        """
        super().__init__(
            agent_type=AgentType.IMAGE_ANALYZER,
            name="ImageAnalyzerAgent",
            config=config
        )
        self.endpoint = endpoint
        
        # Default configuration
        self.default_config = {
            "max_tokens": 2500,
            "temperature": 0.0,  # Deterministic for medical use
            "min_image_quality": 0.3,
            "enable_quality_check": True,
            "use_dedicated_endpoint": True
        }
        
        # Merge with provided config
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value
    
    def validate_input(self, input_data: Any) -> bool:
        """
        Validate input image data.
        
        Args:
            input_data: Should be MedicalImageData or dict with 'image' key
        
        Returns:
            True if valid, False otherwise
        """
        try:
            if isinstance(input_data, MedicalImageData):
                return True
            
            if isinstance(input_data, dict) and "image" in input_data:
                return True
            
            self.logger.error("Invalid input: Expected MedicalImageData or dict with 'image'")
            return False
            
        except Exception as e:
            self.logger.error(f"Input validation error: {str(e)}")
            return False
    
    def _assess_image_quality(self, image: Image.Image) -> Dict:
        """
        Assess the quality of the medical image.
        
        Args:
            image: PIL Image object
        
        Returns:
            Dictionary with quality metrics
        """
        # Basic quality checks
        width, height = image.size
        
        # Check resolution
        min_resolution = 512
        resolution_ok = width >= min_resolution and height >= min_resolution
        
        # Check if image is too small
        if not resolution_ok:
            quality_score = 0.3
        else:
            quality_score = 0.8
        
        # Check aspect ratio (very elongated images might be problematic)
        aspect_ratio = max(width, height) / min(width, height)
        if aspect_ratio > 3.0:
            quality_score *= 0.8
        
        # Check if image is grayscale or color
        is_grayscale = image.mode in ('L', 'LA')
        
        return {
            "score": quality_score,
            "resolution": {"width": width, "height": height},
            "resolution_adequate": resolution_ok,
            "aspect_ratio": aspect_ratio,
            "is_grayscale": is_grayscale,
            "issues": [] if quality_score > 0.6 else ["Low resolution or poor aspect ratio"]
        }
    
    def _build_system_prompt(self, image_type: str = "unknown") -> str:
        """
        Build the system instruction for MedGemma.
        
        Args:
            image_type: Type of medical image
        
        Returns:
            System prompt string
        """
        base_prompt = """
        You are a highly experienced and accurate medical imaging AI, trained to assist radiologists
        in interpreting diagnostic images.

        You are analyzing a medical image. Your role is to generate a clear, clinically useful
        description of the scan, identifying relevant anatomical structures, patterns, anomalies,
        and potential diagnoses. Do not guess or hallucinate findings not evident in the image.

        Focus on:
        - Location and characteristics of any visible abnormalities
        - Indicators of common pathologies (e.g., fractures, infiltrates, masses)
        - Whether the image appears normal or requires further evaluation

        Use formal, clinical language. If the image quality is too poor to analyze, state this clearly.

        Output rules:
        - Return valid JSON only
        - Return only the JSON object, nothing else
        - Frequent error: to add code fences around the JSON object
        - Do not use Markdown
        - Do not include code fences
        - Do not include any text before or after the JSON
        - Include all keys shown below
        - Use empty arrays when appropriate
        - If no abnormalities are detected, set "abnormalities" to an empty array
        - If image quality is too poor, mention this clearly in "summary" and "impression"

        Return the response in exactly this JSON structure:

        {
        "summary": "Brief overview in 2-3 sentences",
        "anatomical_structures": ["structure 1", "structure 2"],
        "findings": [
            {"finding": "Detailed observation 1"},
            {"finding": "Detailed observation 2"}
        ],
        "abnormalities": [
            {"description": "Abnormality 1"},
            {"description": "Abnormality 2"}
        ],
        "impression": "Clinical impression",
        "recommendations": ["Recommendation 1", "Recommendation 2"],
        "image_quality": {
            "assessed": true,
            "quality": "good"
        }
        }
        """
        
        if image_type != "unknown":
            base_prompt += f"\n\nThis image is identified as a {image_type} scan."
        
        return base_prompt
    
    async def _query_medgemma(
        self,
        image_data: MedicalImageData,
        user_query: str = "Analyze this medical image and provide detailed findings."
    ) -> str:
        """
        Query the MedGemma model using ChatCompletion format.
        
        Args:
            image_data: MedicalImageData object
            user_query: User's query about the image
        
        Returns:
            Model response text
        """
        try:
            system_instruction = self._build_system_prompt(image_data.image_type)
            data_url = image_data.get_data_url()
            
            # Build ChatCompletion format request
            instances = [
                {
                    "@requestFormat": "chatCompletions",
                    "messages": [
                        {
                            "role": "system",
                            "content": [{"type": "text", "text": system_instruction}]
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": user_query
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_url}
                                }
                            ]
                        }
                    ],
                    "max_tokens": self.config["max_tokens"],
                    "temperature": self.config["temperature"]
                }
            ]
            
            self.logger.info("Querying MedGemma model with ChatCompletion format...")
            response = self.endpoint.predict(
                instances=instances,
                use_dedicated_endpoint=self.config["use_dedicated_endpoint"]
            )
            
            # The response.predictions is a dict, not a list!
            if response.predictions:
                prediction_data = response.predictions  # Direct access, not [0]
                
                self.logger.info(f"Received prediction data type: {type(prediction_data)}")
                
                # Extract text from ChatCompletion format
                if isinstance(prediction_data, dict) and 'choices' in prediction_data:
                    # ChatCompletion format: extract from choices[0].message.content
                    response_text = prediction_data['choices'][0]['message']['content']
                    self.logger.info(f"✅ Successfully extracted response ({len(response_text)} chars)")
                    self.logger.info(f"✅ Extracted response: {response_text}")
                    return response_text
                elif isinstance(prediction_data, str):
                    # Legacy format: direct string response
                    self.logger.info("Received legacy format response")
                    return prediction_data
                else:
                    # Unknown format
                    self.logger.error(f"Unexpected prediction format: {type(prediction_data)}")
                    self.logger.error(f"Prediction data: {prediction_data}")
                    raise ValueError(f"Unexpected prediction format: {type(prediction_data)}")
            else:
                self.logger.error("No predictions in response")
                self.logger.error(f"Response object: {response}")
                raise ValueError("No prediction returned from model")
                
        except Exception as e:
            self.logger.error(f"❌ MedGemma query failed: {str(e)}")
            # Only log response if it exists
            try:
                if 'response' in locals():
                    self.logger.error(f"Response: {response}")
                    if hasattr(response, 'predictions'):
                        self.logger.error(f"Predictions: {response.predictions}")
            except:
                pass
            raise



    def clean_model_output(self, text: str) -> str:
        text = text.strip()

        # Remove markdown code fences like ```json ... ``` or ``` ... ```
        text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^```\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        return text.strip()


    def extract_json_object(self, text: str) -> dict:
        text = self.clean_model_output(text)

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Fallback: extract first JSON object
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in model response.")

        return json.loads(match.group(0))
        
    def _parse_model_response(self, response_text: str) -> ImageAnalysisResult:
        try:
            data = self.extract_json_object(response_text)



            summary = str(data.get("summary", "")).strip()

            anatomical_structures = data.get("anatomical_structures", [])
            if not isinstance(anatomical_structures, list):
                anatomical_structures = [str(anatomical_structures)]
            anatomical_structures = [str(x).strip() for x in anatomical_structures if str(x).strip()]

            findings_raw = data.get("findings", [])
            detailed_findings = []
            if isinstance(findings_raw, list):
                for item in findings_raw:
                    if isinstance(item, dict):
                        finding_text = str(item.get("finding", "")).strip()
                        if finding_text:
                            detailed_findings.append({"finding": finding_text})
                    elif isinstance(item, str) and item.strip():
                        detailed_findings.append({"finding": item.strip()})

            abnormalities_raw = data.get("abnormalities", [])
            abnormalities = []
            if isinstance(abnormalities_raw, list):
                for item in abnormalities_raw:
                    if isinstance(item, dict):
                        desc = str(item.get("description", "")).strip()
                        if desc:
                            abnormalities.append({"description": desc})
                    elif isinstance(item, str) and item.strip():
                        abnormalities.append({"description": item.strip()})

            impression = str(data.get("impression", "")).strip()

            recommendations_raw = data.get("recommendations", [])
            if not isinstance(recommendations_raw, list):
                recommendations_raw = [str(recommendations_raw)]
            recommendations = [str(x).strip() for x in recommendations_raw if str(x).strip()]

            image_quality = data.get("image_quality", {"assessed": True})
            if not isinstance(image_quality, dict):
                image_quality = {"assessed": True, "quality": str(image_quality)}

            if "assessed" not in image_quality:
                image_quality["assessed"] = True

            # Calculate confidence based on response completeness
            confidence = 0.7
            if summary:
                confidence += 0.1
            if anatomical_structures:
                confidence += 0.1
            if detailed_findings:
                confidence += 0.1

            return ImageAnalysisResult(
                summary=summary,
                detailed_findings=detailed_findings,
                anatomical_structures=anatomical_structures,
                abnormalities=abnormalities,
                image_quality=image_quality,
                confidence=min(confidence, 0.95),
                recommendations=recommendations
            )

        except Exception as ex:
            self.logger.error(f"❌ JSON parsing failed: {str(ex)}")
            # Fallback: keep raw text in summary if JSON parsing fails
            return ImageAnalysisResult(
                summary=response_text.strip(),
                detailed_findings=[],
                anatomical_structures=[],
                abnormalities=[],
                image_quality={"assessed": False},
                confidence=0.4,
                recommendations=[]
            )
    
    async def process(
        self,
        input_data: Any,
        context: Optional[Dict] = None
    ) -> AgentResult:
        """
        Process medical image and return analysis.
        
        Args:
            input_data: MedicalImageData or dict with 'image' and optional 'query'
            context: Optional context with conversation history, etc.
        
        Returns:
            AgentResult with ImageAnalysisResult data
        """
        try:
            # Extract image data
            if isinstance(input_data, MedicalImageData):
                image_data = input_data
                user_query = context.get("query", "Analyze this medical image.") if context else "Analyze this medical image."
            else:
                image = input_data["image"]
                image_type = input_data.get("image_type", "unknown")
                image_data = MedicalImageData(image, image_type)
                user_query = input_data.get("query", "Analyze this medical image.")
            
            # 1. Assess image quality
            if self.config["enable_quality_check"]:
                quality = self._assess_image_quality(image_data.image)
                
                if quality["score"] < self.config["min_image_quality"]:
                    return AgentResult(
                        success=False,
                        data=None,
                        confidence=0.0,
                        error=f"Image quality too low (score: {quality['score']:.2f}). Issues: {', '.join(quality['issues'])}",
                        metadata={"quality_assessment": quality}
                    )
            
            # 2. Query MedGemma
            response_text = await self._query_medgemma(image_data, user_query)
            
            # 3. Parse response
            analysis_result = self._parse_model_response(response_text)
            
            # 4. Add quality assessment to result
            if self.config["enable_quality_check"]:
                analysis_result.image_quality = quality
            
            return AgentResult(
                success=True,
                data=analysis_result.to_dict(),
                confidence=analysis_result.confidence,
                metadata={
                    "image_type": image_data.image_type,
                    "model_response_length": len(response_text)
                },
                sources=["MedGemma Model"]
            )
            
        except Exception as e:
            self.logger.error(f"Image analysis failed: {str(e)}")
            return AgentResult(
                success=False,
                data=None,
                confidence=0.0,
                error=f"Image analysis failed: {str(e)}"
            )
    
    def compare_images(
        self,
        current_image: MedicalImageData,
        previous_image: MedicalImageData
    ) -> Dict:
        """
        Compare two medical images (e.g., current vs. previous scan).
        
        This is a placeholder for future implementation.
        
        Args:
            current_image: Current medical image
            previous_image: Previous medical image
        
        Returns:
            Comparison results
        """
        # TODO: Implement image comparison logic
        self.logger.warning("Image comparison not yet implemented")
        return {
            "comparison_available": False,
            "message": "Image comparison feature coming soon"
        }
