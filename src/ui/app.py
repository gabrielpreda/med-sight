"""
MedSight - Enhanced Medical Image Analysis Application

This is the new main application integrating all components:
- Multi-agent system
- Healthcare guardrails
- Conversational interface
- Multi-modal document processing
"""

import streamlit as st
from io import BytesIO
from PIL import Image
import base64
import PyPDF2
import os
import asyncio
from dotenv import load_dotenv
from google.cloud import aiplatform
import logging

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import MedSight components
from src.agents import Orchestrator
from src.models import (
    PatientData, MedicalImage, ImageType,
    Message, MessageRole, ConversationSession,
    MedicalRecord, RecordType, DocumentFormat
)
from src.conversation import SessionManager, ContextManager, MemoryStore
from src.document_processing.parsers import PDFParser, TextParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title='MedSight - AI Medical Assistant',
    page_icon="images/gemini_avatar.png",
    initial_sidebar_state='auto',
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #3184a0;
        text-align: center;
        margin-bottom: 2rem;
    }
    .disclaimer-box {
        background-color: #fff3cd;
        border-left: 5px solid #ffc107;
        padding: 1rem;
        margin: 1rem 0;
    }
    .emergency-box {
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def initialize_system():
    """Initialize the MedSight system"""
    load_dotenv()
    
    PROJECT_ID = os.getenv("PROJECT_ID")
    REGION = os.getenv("REGION")
    ENDPOINT_ID = os.getenv("ENDPOINT_ID")
    ENDPOINT_REGION = os.getenv("ENDPOINT_REGION")
    
    logger.info("Initializing Vertex AI API")
    aiplatform.init(project=PROJECT_ID, location=REGION)
    
    endpoint = aiplatform.Endpoint(
        endpoint_name=ENDPOINT_ID,
        project=PROJECT_ID,
        location=ENDPOINT_REGION,
    )
    
    # Initialize orchestrator
    orchestrator = Orchestrator(endpoint=endpoint)
    
    # Initialize conversation management
    session_manager = SessionManager()
    context_manager = ContextManager()
    memory_store = MemoryStore()
    
    # Initialize parsers
    pdf_parser = PDFParser()
    text_parser = TextParser()
    
    logger.info("MedSight system initialized successfully")
    
    return {
        'orchestrator': orchestrator,
        'session_manager': session_manager,
        'context_manager': context_manager,
        'memory_store': memory_store,
        'pdf_parser': pdf_parser,
        'text_parser': text_parser
    }


def process_uploaded_image(uploaded_file, image_id: str) -> MedicalImage:
    """Process uploaded image file"""
    image = Image.open(uploaded_file)
    
    # Convert to base64
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    
    # Create MedicalImage
    medical_image = MedicalImage(
        image_id=image_id,
        image_type=ImageType.UNKNOWN,  # Could be inferred from filename or user input
        image_data=img_b64,
        width=image.size[0],
        height=image.size[1]
    )
    
    return medical_image


def process_uploaded_document(uploaded_file, record_id: str) -> MedicalRecord:
    """Process uploaded document file"""
    file_type = uploaded_file.name.split('.')[-1].lower()
    content = ""
    document_format = DocumentFormat.TEXT
    
    try:
        if file_type == 'pdf':
            document_format = DocumentFormat.PDF
            pdf_reader = PyPDF2.PdfReader(uploaded_file)
            text_parts = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            content = "\n\n".join(text_parts)
            
        elif file_type == 'txt':
            document_format = DocumentFormat.TEXT
            stringio = BytesIO(uploaded_file.getvalue())
            content = stringio.read().decode("utf-8")
            
        else:
            # Fallback for other types
            content = f"Uploaded file: {uploaded_file.name}"
            
        return MedicalRecord(
            record_id=record_id,
            record_type=RecordType.OTHER, # Will be inferred by parser later
            document_format=document_format,
            content=content,
            file_path=uploaded_file.name
        )
        
    except Exception as e:
        logger.error(f"Error processing document {uploaded_file.name}: {e}")
        return None


def main():
    """Main application"""
    
    # Initialize system
    system = initialize_system()
    orchestrator = system['orchestrator']
    session_manager = system['session_manager']
    context_manager = system['context_manager']
    memory_store = system['memory_store']
    
    # Header
    st.markdown('<h1 class="main-header">🏥 MedSight - AI Medical Assistant</h1>', unsafe_allow_html=True)
    
    # Disclaimer
    st.markdown("""
    <div class="disclaimer-box">
        <strong>⚕️ MEDICAL DISCLAIMER:</strong> This AI system is for informational purposes only and is not a substitute 
        for professional medical advice, diagnosis, or treatment. Always seek the advice of your physician or other 
        qualified health provider with any questions you may have regarding a medical condition.
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'session_id' not in st.session_state:
        st.session_state.session_id = session_manager.create_session()
        st.session_state.patient_data = PatientData(patient_id="demo_patient")
    
    # Sidebar
    with st.sidebar:
        st.image("images/gemini_avatar.png", width=100)
        st.markdown("### 📁 Upload Files")
        
        # Image upload
        uploaded_images = st.file_uploader(
            "Upload Medical Images",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            help="Upload X-rays, MRIs, CT scans, etc."
        )
        
        if uploaded_images:
            for idx, img_file in enumerate(uploaded_images):
                medical_image = process_uploaded_image(img_file, f"image_{idx}")
                
                # Add to patient data if not already added
                existing_ids = [img.image_id for img in st.session_state.patient_data.images]
                if medical_image.image_id not in existing_ids:
                    st.session_state.patient_data.add_image(medical_image)
                    st.success(f"✅ Added: {img_file.name}")
                
                # Display thumbnail
                st.image(img_file, caption=img_file.name, use_column_width=True)
        
        # Document upload
        uploaded_docs = st.file_uploader(
            "Upload Medical Records",
            type=["pdf", "txt"],
            accept_multiple_files=True,
            help="Upload medical records, visit notes, lab results, etc."
        )
        
        if uploaded_docs:
            for idx, doc_file in enumerate(uploaded_docs):
                medical_record = process_uploaded_document(doc_file, f"doc_{idx}")
                
                if medical_record and medical_record.content.strip():
                     # Add to patient data if not already added
                    existing_ids = [rec.record_id for rec in st.session_state.patient_data.records]
                    if medical_record.record_id not in existing_ids:
                        st.session_state.patient_data.add_record(medical_record)
                        st.success(f"✅ Added: {doc_file.name}")
                    
                    st.info(f"📄Parsed {len(medical_record.content)} chars from {doc_file.name}")
                else:
                    st.error(f"Failed to process {doc_file.name}")
        
        st.markdown("---")
        
        # Session info
        st.markdown("### 📊 Session Info")
        session = session_manager.get_session(st.session_state.session_id)
        if session:
            st.write(f"Messages: {len(session.messages)}")
            st.write(f"Images: {len(st.session_state.patient_data.images)}")
            st.write(f"Records: {len(st.session_state.patient_data.records)}")
        
        # Clear button
        if st.button("🗑️ Clear Session"):
            st.session_state.session_id = session_manager.create_session()
            st.session_state.patient_data = PatientData(patient_id="demo_patient")
            st.rerun()
    
    # Main chat interface
    st.markdown("### 💬 Conversation")
    
    # Display conversation history
    session = session_manager.get_session(st.session_state.session_id)
    
    if session and session.messages:
        for msg in session.messages:
            with st.chat_message(msg.role):
                st.markdown(msg.content)
                if msg.images:
                    st.caption(f"📷 {len(msg.images)} image(s) attached")
    else:
        with st.chat_message("assistant"):
            st.markdown("Hello! I'm MedSight, your AI medical assistant. How may I help you today?")
    
    # Chat input
    if prompt := st.chat_input("Ask about medical images, records, or medical questions..."):
        # Add user message
        user_message = Message(
            role=MessageRole.USER,
            content=prompt
        )
        session_manager.add_message(st.session_state.session_id, user_message)
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Process with orchestrator
        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                # Prepare input for orchestrator
                conversation_history = [
                    {'role': msg.role, 'content': msg.content}
                    for msg in session.messages
                ]
                
                orchestrator_input = {
                    'query': prompt,
                    'patient_data': st.session_state.patient_data,
                    'conversation_history': conversation_history
                }
                
                # Run orchestrator (async)
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(
                        orchestrator.execute(orchestrator_input)
                    )
                    loop.close()
                    
                    if result.success:
                        response_text = result.data.get('answer', 'No response generated.')
                        
                        # Display response
                        st.markdown(response_text)
                        
                        # Show confidence if available
                        if result.confidence:
                            confidence_pct = result.confidence * 100
                            st.caption(f"Confidence: {confidence_pct:.1f}%")
                        
                        # Add assistant message
                        assistant_message = Message(
                            role=MessageRole.ASSISTANT,
                            content=response_text
                        )
                        session_manager.add_message(st.session_state.session_id, assistant_message)
                        
                    else:
                        error_msg = f"⚠️ Error: {result.error}"
                        st.error(error_msg)
                        
                        assistant_message = Message(
                            role=MessageRole.ASSISTANT,
                            content=error_msg
                        )
                        session_manager.add_message(st.session_state.session_id, assistant_message)
                
                except Exception as e:
                    logger.error(f"Error processing request: {e}", exc_info=True)
                    st.error(f"An error occurred: {str(e)}")
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9rem;'>
        MedSight v2.0 | Powered by MedGemma | Built with ❤️ for Healthcare
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
