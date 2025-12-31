# MedSight Architecture Recommendations

## Current State Analysis

### Existing Architecture
The current MedSight application is a **simple Streamlit-based medical image analysis tool** with:
- Single-turn image analysis using MedGemma model
- Basic UI with image upload capability
- Direct endpoint prediction without conversation history
- No guardrails or safety mechanisms
- No multi-modal document processing
- No agentic capabilities

### Technology Stack
- **Frontend/Backend**: Streamlit (monolithic)
- **Model**: MedGemma (deployed on Vertex AI)
- **Deployment**: Google App Engine
- **Input**: Single medical images only

---

## Proposed Architecture Modifications

### 1. Healthcare Domain Guardrails

#### 1.1 Input Validation Layer
Create a dedicated guardrails module to ensure safety and compliance:

```
src/
├── guardrails/
│   ├── __init__.py
│   ├── input_validator.py      # Validate user inputs
│   ├── output_validator.py     # Validate model outputs
│   ├── safety_checker.py       # Medical safety checks
│   ├── compliance_checker.py   # HIPAA/regulatory compliance
│   └── config/
│       ├── allowed_queries.yaml
│       ├── blocked_patterns.yaml
│       └── medical_disclaimers.yaml
```

**Key Features:**
- **Input Sanitization**: Remove PII, validate medical terminology
- **Query Classification**: Identify diagnostic vs. informational queries
- **Safety Boundaries**: Block requests for:
  - Treatment recommendations without disclaimer
  - Diagnosis without "preliminary findings" framing
  - Prescription or dosage information
  - Emergency medical advice (redirect to emergency services)
- **Output Filtering**: 
  - Add medical disclaimers automatically
  - Flag uncertain findings with confidence scores
  - Prevent definitive diagnostic language
- **Audit Logging**: Track all interactions for compliance

#### 1.2 Medical Context Validator
```python
# Example implementation structure
class MedicalGuardrails:
    def validate_input(self, query: str, image: bytes) -> ValidationResult:
        """Validate medical query and image quality"""
        
    def validate_output(self, response: str) -> str:
        """Add disclaimers and validate medical safety"""
        
    def check_emergency(self, query: str) -> bool:
        """Detect emergency situations"""
        
    def add_disclaimer(self, response: str, query_type: str) -> str:
        """Add appropriate medical disclaimers"""
```

---

### 2. Conversational Application Architecture

#### 2.1 Multi-Turn Conversation Management
Transform from single-turn to conversational:

```
src/
├── conversation/
│   ├── __init__.py
│   ├── session_manager.py      # Manage conversation sessions
│   ├── context_manager.py      # Track conversation context
│   ├── memory_store.py         # Store conversation history
│   └── retrieval.py            # Retrieve relevant context
```

**Key Changes:**
- **Session State**: Persistent conversation tracking
- **Context Window**: Maintain last N turns with images
- **Reference Resolution**: Handle "the previous scan", "that finding"
- **Multi-Image Comparison**: Compare current vs. previous scans
- **Follow-up Questions**: Enable clarification and deeper analysis

#### 2.2 Enhanced Message Structure
```python
class ConversationMessage:
    role: str  # "user" | "assistant" | "system"
    content: str
    images: List[ImageData]  # Multiple images per turn
    documents: List[DocumentData]  # Medical records
    metadata: Dict  # Timestamps, confidence, sources
    references: List[str]  # References to previous messages
```

#### 2.3 Conversation Flow
```
User Input → Guardrails → Context Retrieval → Agent Processing → 
Output Validation → Response with Disclaimer → Update Context
```

---

### 3. ADK Agentic Functionality

#### 3.1 Multi-Agent Architecture
Implement specialized agents using Agent Development Kit patterns:

```
src/
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py         # Main agent coordinator
│   ├── image_analyzer_agent.py # Medical image analysis
│   ├── record_parser_agent.py  # Parse medical records
│   ├── synthesis_agent.py      # Combine multi-modal insights
│   ├── qa_agent.py             # Answer follow-up questions
│   └── routing_agent.py        # Route to appropriate agent
```

#### 3.2 Agent Roles

**A. Routing Agent**
- Classifies incoming requests
- Routes to appropriate specialist agent
- Determines if multi-agent collaboration needed

**B. Image Analyzer Agent**
- Analyzes medical images using MedGemma
- Identifies anatomical structures
- Detects abnormalities
- Generates structured findings

**C. Record Parser Agent**
- Extracts information from medical records
- Parses visit notes, lab results
- Structures unstructured medical text
- Identifies relevant patient history

**D. Synthesis Agent**
- Combines image findings with medical records
- Correlates imaging with clinical history
- Generates comprehensive reports
- Identifies discrepancies or confirmations

**E. QA Agent**
- Handles follow-up questions
- Retrieves specific information
- Clarifies findings
- Provides educational context

#### 3.3 Agent Workflow Example
```python
class MedicalOrchestrator:
    def process_request(self, 
                       query: str,
                       images: List[Image],
                       documents: List[Document],
                       conversation_history: List[Message]) -> Response:
        
        # 1. Route request
        task_type = self.routing_agent.classify(query)
        
        # 2. Execute appropriate workflow
        if task_type == "image_analysis":
            findings = self.image_analyzer.analyze(images)
            
        elif task_type == "comprehensive_review":
            # Multi-agent collaboration
            image_findings = self.image_analyzer.analyze(images)
            clinical_context = self.record_parser.extract(documents)
            synthesis = self.synthesis_agent.combine(
                image_findings, 
                clinical_context
            )
            return synthesis
            
        elif task_type == "follow_up":
            return self.qa_agent.answer(query, conversation_history)
```

#### 3.4 Reflexion Loop for Quality
Implement self-reflection for improved accuracy:

```python
class ReflexionAgent:
    def refine_analysis(self, 
                       initial_findings: str,
                       image: Image,
                       medical_records: List[Document]) -> str:
        """
        Self-critique and refine medical analysis
        """
        # 1. Generate initial analysis
        analysis = initial_findings
        
        # 2. Self-critique
        critique = self.critique_findings(analysis, image)
        
        # 3. Check against medical records
        consistency = self.check_consistency(analysis, medical_records)
        
        # 4. Refine if needed
        if critique.needs_refinement or not consistency.is_consistent:
            refined = self.refine(analysis, critique, consistency)
            return refined
            
        return analysis
```

---

### 4. Multi-Modal Document Processing

#### 4.1 Document Processing Pipeline
```
src/
├── document_processing/
│   ├── __init__.py
│   ├── parsers/
│   │   ├── pdf_parser.py       # Parse PDF medical records
│   │   ├── dicom_parser.py     # Parse DICOM images
│   │   ├── hl7_parser.py       # Parse HL7 messages
│   │   └── text_parser.py      # Parse text notes
│   ├── extractors/
│   │   ├── metadata_extractor.py
│   │   ├── entity_extractor.py  # Extract medical entities
│   │   └── timeline_builder.py  # Build patient timeline
│   └── integrators/
│       ├── image_record_linker.py
│       └── multi_modal_fusion.py
```

#### 4.2 Supported Document Types
- **Medical Images**: DICOM, PNG, JPEG (X-rays, MRI, CT, etc.)
- **Medical Records**: PDF, HL7, FHIR
- **Clinical Notes**: Text, PDF
- **Lab Results**: Structured data (JSON, XML, CSV)
- **Visit Notes**: Text documents

#### 4.3 Multi-Modal Fusion Strategy
```python
class MultiModalProcessor:
    def process_patient_data(self,
                            images: List[MedicalImage],
                            records: List[MedicalRecord],
                            notes: List[ClinicalNote]) -> PatientInsight:
        """
        Combine multiple data sources for comprehensive analysis
        """
        # 1. Parse all documents
        parsed_images = [self.parse_image(img) for img in images]
        parsed_records = [self.parse_record(rec) for rec in records]
        parsed_notes = [self.parse_note(note) for note in notes]
        
        # 2. Extract entities and timeline
        timeline = self.build_timeline(parsed_records, parsed_notes)
        entities = self.extract_entities(parsed_records, parsed_notes)
        
        # 3. Link images to clinical context
        linked_data = self.link_images_to_context(
            parsed_images, 
            timeline, 
            entities
        )
        
        # 4. Generate comprehensive insight
        insight = self.synthesis_agent.generate_insight(linked_data)
        
        return insight
```

---

## Recommended Project Structure

```
med-sight/
├── .env
├── .gitignore
├── README.md
├── ARCHITECTURE_RECOMMENDATIONS.md
├── requirements.txt
├── app.yaml
├── pyproject.toml                    # New: Project configuration
│
├── config/                            # New: Configuration files
│   ├── agents.yaml
│   ├── guardrails.yaml
│   └── models.yaml
│
├── data/                              # New: Sample data for testing
│   ├── sample_images/
│   └── sample_records/
│
├── src/                               # New: Source code organization
│   ├── __init__.py
│   │
│   ├── agents/                        # Agentic functionality
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── orchestrator.py
│   │   ├── image_analyzer_agent.py
│   │   ├── record_parser_agent.py
│   │   ├── synthesis_agent.py
│   │   ├── qa_agent.py
│   │   └── routing_agent.py
│   │
│   ├── guardrails/                    # Healthcare guardrails
│   │   ├── __init__.py
│   │   ├── input_validator.py
│   │   ├── output_validator.py
│   │   ├── safety_checker.py
│   │   ├── compliance_checker.py
│   │   └── config/
│   │       ├── allowed_queries.yaml
│   │       ├── blocked_patterns.yaml
│   │       └── disclaimers.yaml
│   │
│   ├── conversation/                  # Conversation management
│   │   ├── __init__.py
│   │   ├── session_manager.py
│   │   ├── context_manager.py
│   │   ├── memory_store.py
│   │   └── retrieval.py
│   │
│   ├── document_processing/           # Multi-modal processing
│   │   ├── __init__.py
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── pdf_parser.py
│   │   │   ├── dicom_parser.py
│   │   │   ├── hl7_parser.py
│   │   │   └── text_parser.py
│   │   ├── extractors/
│   │   │   ├── __init__.py
│   │   │   ├── metadata_extractor.py
│   │   │   ├── entity_extractor.py
│   │   │   └── timeline_builder.py
│   │   └── integrators/
│   │       ├── __init__.py
│   │       ├── image_record_linker.py
│   │       └── multi_modal_fusion.py
│   │
│   ├── models/                        # Data models
│   │   ├── __init__.py
│   │   ├── message.py
│   │   ├── patient_data.py
│   │   ├── medical_image.py
│   │   └── medical_record.py
│   │
│   ├── utils/                         # Utilities
│   │   ├── __init__.py
│   │   ├── image_utils.py
│   │   ├── text_utils.py
│   │   └── logging_utils.py
│   │
│   └── ui/                            # UI components
│       ├── __init__.py
│       ├── app.py                     # Main Streamlit app
│       ├── components/
│       │   ├── chat_interface.py
│       │   ├── file_uploader.py
│       │   └── results_display.py
│       └── styles/
│           └── custom.css
│
├── tests/                             # New: Test suite
│   ├── __init__.py
│   ├── test_agents/
│   ├── test_guardrails/
│   ├── test_conversation/
│   └── test_document_processing/
│
├── docs/                              # New: Documentation
│   ├── architecture.md
│   ├── api_reference.md
│   ├── user_guide.md
│   └── deployment.md
│
└── images/                            # UI assets
    ├── gemini_avatar.png
    ├── user_avatar.png
    └── med-sight.png
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
1. **Restructure project** into modular architecture
2. **Implement basic guardrails**:
   - Input validation
   - Output disclaimers
   - Emergency detection
3. **Set up conversation management**:
   - Session tracking
   - Context storage
   - Message history

### Phase 2: Agentic Core (Week 3-4)
1. **Implement base agent framework**
2. **Create specialized agents**:
   - Image Analyzer Agent
   - Record Parser Agent
   - Routing Agent
3. **Build orchestrator** for agent coordination
4. **Add reflexion loop** for quality improvement

### Phase 3: Multi-Modal Processing (Week 5-6)
1. **Implement document parsers**:
   - PDF parser
   - DICOM parser
   - Text parser
2. **Build entity extraction**
3. **Create timeline builder**
4. **Implement multi-modal fusion**

### Phase 4: Integration & Testing (Week 7-8)
1. **Integrate all components**
2. **Comprehensive testing**
3. **UI/UX improvements**
4. **Performance optimization**
5. **Documentation**

---

## Key Dependencies to Add

```txt
# Existing
google==3.0.0
google-cloud-core==2.4.1
google-cloud-aiplatform==1.99.0
streamlit==1.28.0
gunicorn==20.0.4
python-dotenv==1.0.0

# New - Agentic Framework
langchain==0.1.0
langchain-google-vertexai==0.1.0
langgraph==0.0.20

# New - Document Processing
pypdf2==3.0.1
python-docx==1.1.0
pydicom==2.4.4
hl7==0.4.5
python-fhir==0.2.0

# New - Data Processing
pandas==2.1.4
numpy==1.26.2
pillow==10.1.0

# New - Medical NLP
spacy==3.7.2
scispacy==0.5.3
medcat==1.9.0

# New - Validation & Safety
pydantic==2.5.0
jsonschema==4.20.0

# New - Storage & Caching
redis==5.0.1
sqlalchemy==2.0.23

# New - Testing
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
```

---

## Security & Compliance Considerations

### HIPAA Compliance
1. **Data Encryption**: Encrypt all patient data at rest and in transit
2. **Access Controls**: Implement role-based access control (RBAC)
3. **Audit Logging**: Log all access to patient data
4. **Data Retention**: Implement proper data retention policies
5. **De-identification**: Support PHI de-identification

### Safety Measures
1. **Disclaimer System**: Automatic medical disclaimers on all outputs
2. **Confidence Scoring**: Show confidence levels for findings
3. **Human-in-the-Loop**: Flag uncertain cases for human review
4. **Emergency Detection**: Detect and escalate emergency situations
5. **Bias Detection**: Monitor for potential bias in recommendations

---

## Performance Optimization

### Caching Strategy
- **Model Response Caching**: Cache similar image analyses
- **Document Parsing Cache**: Cache parsed medical records
- **Conversation Context**: Efficient context retrieval

### Scalability
- **Async Processing**: Use async/await for I/O operations
- **Batch Processing**: Support batch image analysis
- **Load Balancing**: Distribute agent workload
- **Database Optimization**: Efficient conversation storage

---

## Monitoring & Observability

### Metrics to Track
1. **Response Time**: Agent processing time
2. **Accuracy**: Validation against ground truth
3. **User Satisfaction**: Feedback scores
4. **Safety Events**: Guardrail triggers
5. **System Health**: Error rates, uptime

### Logging Strategy
```python
# Structured logging for medical applications
{
    "timestamp": "2025-12-31T16:30:00Z",
    "session_id": "uuid",
    "user_id": "hashed_id",
    "agent": "image_analyzer",
    "action": "analyze_xray",
    "input_hash": "sha256_hash",
    "output_hash": "sha256_hash",
    "confidence": 0.85,
    "guardrails_triggered": ["disclaimer_added"],
    "processing_time_ms": 1250
}
```

---

## Next Steps

1. **Review this architecture** with your team
2. **Prioritize features** based on your use case
3. **Start with Phase 1** (Foundation)
4. **Set up development environment** with new dependencies
5. **Create implementation plan** with specific tasks

Would you like me to start implementing any specific component?
