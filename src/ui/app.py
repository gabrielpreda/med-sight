"""
MedSight — AI Medical Assistant (ADK Edition)

Streamlit UI that drives the Google ADK multi-agent pipeline.
"""

import asyncio
import base64
import logging
import os
import uuid
import json
from io import BytesIO

import PyPDF2
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

# Add project root to sys.path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

load_dotenv()

# ADK runtime
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

# MedSight ADK agent
from src.agents import root_agent
from src.agents.tools.medical_tools import analyze_medical_image, is_valid_json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MedSight – AI Medical Assistant",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
* { font-family: 'Inter', sans-serif; }

.main-header {
    font-size: 2.4rem;
    font-weight: 700;
    background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    margin-bottom: 0.5rem;
}
.subtitle {
    text-align: center;
    color: #5f6368;
    font-size: 1rem;
    margin-bottom: 1.5rem;
}
.disclaimer-box {
    background: linear-gradient(135deg, #fff8e1 0%, #fff3cd 100%);
    border-left: 5px solid #ffc107;
    border-radius: 0 8px 8px 0;
    padding: 0.9rem 1.2rem;
    margin: 0.8rem 0 1.4rem 0;
    font-size: 0.88rem;
    color: #5f4b00;
}
.emergency-box {
    background: linear-gradient(135deg, #fde8e8 0%, #f8d7da 100%);
    border-left: 5px solid #dc3545;
    border-radius: 0 8px 8px 0;
    padding: 1rem 1.2rem;
    font-weight: 600;
    color: #721c24;
}
.badge {
    display: inline-block;
    background: #e8f0fe;
    color: #1a73e8;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 0.78rem;
    font-weight: 500;
    margin: 2px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# ADK runner (cached so it persists across reruns)
# ---------------------------------------------------------------------------
APP_NAME = "medsight"

@st.cache_resource
def get_runner() -> Runner:
    """Create and cache the ADK Runner + session service."""
    session_service = InMemorySessionService()
    return Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )


def get_or_create_session(runner: Runner) -> str:
    """Ensure a stable session_id is stored in Streamlit session state."""
    if "adk_session_id" not in st.session_state:
        sid = str(uuid.uuid4())
        st.session_state["adk_session_id"] = sid
        asyncio.run(
            runner.session_service.create_session(
                app_name=APP_NAME,
                user_id="streamlit_user",
                session_id=sid,
                state={},
            )
        )
    return st.session_state["adk_session_id"]


# ---------------------------------------------------------------------------
# File processing helpers
# ---------------------------------------------------------------------------

def process_image_upload(uploaded_file) -> str:
    """Return base64-encoded PNG string from an uploaded image."""
    img = Image.open(uploaded_file).convert("RGB")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def process_document_upload(uploaded_file) -> str:
    """Extract text from PDF or TXT upload."""
    ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        reader = PyPDF2.PdfReader(uploaded_file)
        pages = [p.extract_text() or "" for p in reader.pages]
        return "\n\n".join(pages)
    else:
        return BytesIO(uploaded_file.getvalue()).read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# ADK call wrapper
# ---------------------------------------------------------------------------

async def run_agent_async(runner: Runner, session_id: str, message: str) -> str:
    user_content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=message)],
    )

    final_text = ""
    tool_outputs = []

    async for event in runner.run_async(
        user_id="streamlit_user",
        session_id=session_id,
        new_message=user_content,
    ):
        logger.warning("ADK EVENT: %s", event)

        if event.content and event.content.parts:
            for part in event.content.parts:
                text = getattr(part, "text", None)
                if text:
                    final_text += text

                function_call = getattr(part, "function_call", None)
                if function_call:
                    logger.warning("ADK FUNCTION CALL: %s", function_call)

                function_response = getattr(part, "function_response", None)
                if function_response:
                    logger.warning("ADK FUNCTION RESPONSE: %s", function_response)
                    tool_outputs.append(str(function_response.response))

    if final_text.strip():
        return final_text.strip()

    if tool_outputs:
        return "\n\n".join(tool_outputs)

    return "No response generated."


def run_agent(runner: Runner, session_id: str, message: str) -> str:
    """Synchronous wrapper around run_agent_async for Streamlit."""
    return asyncio.run(run_agent_async(runner, session_id, message))


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------

def build_prompt(
    query: str,
    image_b64: str = "",
    record_content: str = "",
) -> str:
    """
    Build the full prompt sent to the ADK agent, embedding any uploaded
    image/document as context alongside the user query.
    """
    parts = [f"User question: {query}"]

    if image_b64:
        parts.append(
            "\n[CONTEXT] A medical image has been uploaded. "
            "Call analyze_medical_image with exactly these arguments:\n"
            f"image_b64 = {json.dumps(image_b64)}\n"
            f"image_type = {json.dumps(st.session_state.get('image_type', 'unknown'))}\n"
            f"query = {json.dumps(query)}"
        )
    if record_content:
        parts.append(
            f"\n[CONTEXT] A medical record/document has been uploaded.\n"
            f"Use the parse_medical_record tool with the following content:\n"
            f"---\n{record_content[:3000]}\n---"
        )

    if image_b64 and record_content:
        parts.append(
            "\nAfter analyzing both the image and the record, use synthesize_findings "
            "to produce a comprehensive report."
        )

    return "\n".join(parts)


def main():
    runner     = get_runner()
    session_id = get_or_create_session(runner)

    # --- Header ---
    st.markdown('<h1 class="main-header">🏥 MedSight</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">AI-Powered Medical Image & Record Analysis — Powered by Google ADK + MedGemma</p>', unsafe_allow_html=True)

    st.markdown("""
    <div class="disclaimer-box">
        <strong>⚕️ MEDICAL DISCLAIMER:</strong> This AI system is for <strong>informational purposes only</strong>
        and is NOT a substitute for professional medical advice, diagnosis, or treatment.
        Always seek the advice of your physician or qualified health provider.
    </div>
    """, unsafe_allow_html=True)

    # --- Sidebar: uploads ---
    with st.sidebar:
        try:
            st.image("images/gemini_avatar.png", width=90)
        except Exception:
            st.markdown("### 🏥 MedSight")

        st.markdown("## 📁 Upload Files")

        # Image upload
        st.markdown("### 🩻 Medical Image")
        uploaded_image = st.file_uploader(
            "Upload X-ray, MRI, CT scan…",
            type=["jpg", "jpeg", "png"],
            key="img_uploader",
        )
        image_type_options = ["unknown", "xray", "mri", "ct", "ultrasound", "pathology"]
        image_type = st.selectbox("Image type", image_type_options, key="image_type")

        if uploaded_image:
            st.image(uploaded_image, caption=uploaded_image.name, use_column_width=True)
            if "uploaded_image_b64" not in st.session_state or st.session_state.get("_last_img") != uploaded_image.name:
                st.session_state["uploaded_image_b64"] = process_image_upload(uploaded_image)
                st.session_state["_last_img"] = uploaded_image.name
                st.success(f"✅ Image loaded: {uploaded_image.name}")

        # Document upload
        st.markdown("### 📄 Medical Record")
        uploaded_doc = st.file_uploader(
            "Upload PDF or TXT record",
            type=["pdf", "txt"],
            key="doc_uploader",
        )
        if uploaded_doc:
            if "uploaded_record_content" not in st.session_state or st.session_state.get("_last_doc") != uploaded_doc.name:
                st.session_state["uploaded_record_content"] = process_document_upload(uploaded_doc)
                st.session_state["_last_doc"] = uploaded_doc.name
            char_count = len(st.session_state["uploaded_record_content"])
            st.success(f"✅ Record loaded: {uploaded_doc.name} ({char_count:,} chars)")

        st.markdown("---")

        # Session stats
        st.markdown("### 📊 Session")
        history = st.session_state.get("chat_history", [])
        col1, col2 = st.columns(2)
        col1.metric("Messages", len(history))
        col2.metric(
            "Files",
            int(bool(st.session_state.get("uploaded_image_b64"))) +
            int(bool(st.session_state.get("uploaded_record_content")))
        )

        if st.button("🗑️ Clear Session", use_container_width=True):
            for key in ["chat_history", "uploaded_image_b64", "uploaded_record_content",
                        "_last_img", "_last_doc", "adk_session_id"]:
                st.session_state.pop(key, None)
            st.rerun()

    # --- Chat history ---
    st.markdown("### 💬 Conversation")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    if not st.session_state["chat_history"]:
        with st.chat_message("assistant"):
            st.markdown(
                "Hello! I'm **MedSight**, your AI medical assistant. "
                "Upload medical images or records in the sidebar, then ask me a question. "
                "I can analyze imaging, parse clinical documents, and answer medical questions."
            )

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # --- Chat input ---
    if prompt := st.chat_input("Ask about medical images, records, or medical questions…"):
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state["chat_history"].append({"role": "user", "content": prompt})

        # Build full prompt with any uploaded context
        full_prompt = build_prompt(
            query          = prompt,
            image_b64      = st.session_state.get("uploaded_image_b64", ""),
            record_content = st.session_state.get("uploaded_record_content", ""),
        )

        image_response = None
        # Call ADK agent
        with st.chat_message("assistant"):
            with st.spinner("🔬 Analyzing…"):
                try:
                    if st.session_state.get("uploaded_image_b64"):
                        image_response = analyze_medical_image(
                            image_b64=st.session_state["uploaded_image_b64"],
                            image_type=st.session_state.get("image_type", "unknown"),
                            query=prompt,
                            provider="ollama",
                        )

                    if is_valid_json(image_response):
                        st.json(image_response)
                        response = image_response
                    
                    if st.session_state.get("uploaded_record_content") and image_response:
                        record_content = st.session_state.get("uploaded_record_content", "")

                        full_prompt = build_prompt(
                            query          = f"{prompt}; Image analysis: {image_response}",
                            record_content = record_content,
                        )
                        response = run_agent(runner, session_id, full_prompt)

                    else:
                        full_prompt = build_prompt(
                            query          = prompt,
                            record_content = st.session_state.get("uploaded_record_content", ""),
                        )
                        response = run_agent(runner, session_id, full_prompt)
        
                    st.markdown(response)
                    
                    st.session_state["chat_history"].append({"role": "assistant", "content": response})

                    # Show active tools badge
                    active = []
                    if st.session_state.get("uploaded_image_b64"):
                        active.append("🩻 Image Analysis")
                    if st.session_state.get("uploaded_record_content"):
                        active.append("📄 Record Parsing")
                    if active:
                        st.markdown(" ".join(f'<span class="badge">{a}</span>' for a in active), unsafe_allow_html=True)

                except Exception as exc:
                    logger.error("Agent error: %s", exc, exc_info=True)
                    st.error(f"An error occurred: {exc}")

    # --- Footer ---
    st.markdown("---")
    st.markdown(
        "<div style='text-align:center;color:#9aa0a6;font-size:0.82rem;'>"
        "MedSight v3.0 · Google ADK · MedGemma · Gemini · Built with ❤️ for Healthcare"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
