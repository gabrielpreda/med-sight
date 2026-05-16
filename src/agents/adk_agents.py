"""
MedSight ADK Multi-Agent System

Architecture
============

  [before_agent_callback: guardrail_callback]
        │
        │  MEDICAL → proceed
        │  PSEUDOMEDICINE / NON_MEDICAL → abort immediately with refusal
        ↓
  root_agent  (LlmAgent — orchestrator / router)
    │
    ├── AgentTool ──► image_analyzer_agent   (LlmAgent + analyze_medical_image)
    ├── AgentTool ──► record_parser_agent    (LlmAgent + parse_medical_record)
    ├── AgentTool ──► qa_agent               (LlmAgent + answer_medical_question)
    └── AgentTool ──► synthesis_agent        (LlmAgent + synthesize_findings)

Vertex AI backend is configured by medical_tools._configure_backend()
which reads USE_VERTEX_AI / PROJECT_ID / REGION from .env.
"""

import json
import logging
from typing import Optional

# medical_tools must be imported first so _configure_backend() runs
# before any google-genai / ADK code inspects the environment.
from .tools.medical_tools import (
    analyze_medical_image,
    parse_medical_record,
    answer_medical_question,
    synthesize_findings,
    check_medical_relevance,
)

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.agent_tool import AgentTool
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model names
# ---------------------------------------------------------------------------
_FLASH   = "gemini-2.5-flash"
_FLASH_L = "gemini-2.5-flash-lite"


# ---------------------------------------------------------------------------
# Guardrail callback  –  runs before root_agent on every user turn
# ---------------------------------------------------------------------------

def guardrail_callback(callback_context: CallbackContext) -> Optional[genai_types.Content]:
    """
    ADK before_agent_callback that acts as the system's front-door guardrail.

    Extracts the latest user message, runs it through check_medical_relevance(),
    and — if the query is about pseudomedicine or is entirely non-medical —
    returns a refusal Content immediately, preventing any sub-agent from running.

    Returns:
        None  → query is medical; pipeline continues normally.
        Content → query is rejected; agent pipeline is short-circuited.
    """
    # Extract user text from the invocation context
    user_text = ""
    try:
        user_content = callback_context._invocation_context.user_content
        if user_content and user_content.parts:
            user_text = " ".join(
                p.text for p in user_content.parts if hasattr(p, "text") and p.text
            ).strip()
    except Exception as exc:
        logger.debug("guardrail_callback: could not extract user text: %s", exc)

    if not user_text:
        return None  # nothing to check → allow through

    # Run the two-layer classifier
    try:
        result = json.loads(check_medical_relevance(user_text))
    except Exception as exc:
        logger.warning("guardrail_callback: classifier error, allowing through: %s", exc)
        return None

    verdict = result.get("verdict", "MEDICAL")
    allowed = result.get("allowed", True)
    reason  = result.get("reason", "")

    if allowed:
        logger.info("Guardrail PASSED [%s] for query: %.80s…", verdict, user_text)
        return None  # allow → pipeline continues

    # Build a firm, polite refusal
    logger.warning(
        "Guardrail BLOCKED [%s] query: %.80s… | reason: %s",
        verdict, user_text, reason,
    )

    if verdict == "PSEUDOMEDICINE":
        icon    = "🚫"
        heading = "Request Outside Evidence-Based Medicine"
        body    = (
            f"{reason}\n\n"
            "MedSight is built on peer-reviewed, evidence-based medical science. "
            "It does not support, evaluate, or recommend treatments that lack "
            "scientific validation. If you have health concerns, please consult "
            "a licensed healthcare professional."
        )
    else:  # NON_MEDICAL
        icon    = "⛔"
        heading = "Request Outside Medical Scope"
        body    = (
            f"{reason}\n\n"
            "MedSight can only assist with:\n"
            "• Medical image analysis (X-ray, MRI, CT, ultrasound)\n"
            "• Clinical document parsing (records, reports, lab results)\n"
            "• Evidence-based medical questions\n\n"
            "Please ask a medically relevant question."
        )

    refusal_text = f"{icon} **{heading}**\n\n{body}"

    return genai_types.Content(
        role="model",
        parts=[genai_types.Part(text=refusal_text)],
    )


# ---------------------------------------------------------------------------
# 1.  Image Analyzer Agent
# ---------------------------------------------------------------------------
image_analyzer_agent = LlmAgent(
    model=_FLASH,
    name="ImageAnalyzerAgent",
    description=(
        "Specialized medical imaging AI. "
        "Receives a base64-encoded image and an optional clinical question, "
        "calls the MedGemma model on Vertex AI, and returns a structured "
        "JSON analysis (findings, abnormalities, impression, recommendations)."
    ),
    instruction="""
You are a specialist medical imaging AI trained to assist radiologists.

When given an image and a question:
1. Call analyze_medical_image with the provided image_b64, image_type, and query.
2. Parse the JSON result.
3. Present the findings clearly using this structure:
   - **Summary** – brief overview
   - **Key Findings** – bullet list
   - **Abnormalities** – if any, list with descriptions
   - **Impression** – clinical impression
   - **Recommendations** – next steps

Always end with:
"⚠️ This analysis is AI-generated and must be reviewed by a qualified radiologist."
""",
    tools=[analyze_medical_image],
)


# ---------------------------------------------------------------------------
# 2.  Record Parser Agent
# ---------------------------------------------------------------------------
record_parser_agent = LlmAgent(
    model=_FLASH,
    name="RecordParserAgent",
    description=(
        "Medical record extraction specialist. "
        "Parses clinical documents (text / PDF content) and returns structured "
        "data: diagnoses, medications, procedures, dates, summary."
    ),
    instruction="""
You are a clinical NLP specialist that extracts structured information from medical records.

When given a document:
1. Call parse_medical_record with the full document content.
2. Parse the JSON result.
3. Present the extracted information clearly:
   - **Diagnoses** – confirmed diagnoses
   - **Medications** – current medications
   - **Procedures** – procedures performed or scheduled
   - **Key Dates** – relevant dates
   - **Summary** – professional summary
   - **⚠️ Critical Flags** – if any

Always end with:
"⚠️ This extraction is AI-assisted. Please verify with the original document."
""",
    tools=[parse_medical_record],
)


# ---------------------------------------------------------------------------
# 3.  QA Agent
# ---------------------------------------------------------------------------
qa_agent = LlmAgent(
    model=_FLASH,
    name="QAAgent",
    description=(
        "Medical question-answering agent. "
        "Answers general medical questions and follow-up questions using "
        "conversation history as context."
    ),
    instruction="""
You are a knowledgeable medical AI assistant.

When answering a question:
1. Call answer_medical_question with the query and conversation_history_json.
2. Parse the JSON result to get the core answer.
3. Enrich the answer with clear, empathetic, professional language.
4. If the question is about a medical emergency, respond IMMEDIATELY:
   "🚨 EMERGENCY: Call 911 or go to the nearest emergency room immediately."

Always end with:
"⚠️ This information is educational only. Please consult a healthcare professional for personal medical advice."
""",
    tools=[answer_medical_question],
)


# ---------------------------------------------------------------------------
# 4.  Synthesis Agent
# ---------------------------------------------------------------------------
synthesis_agent = LlmAgent(
    model=_FLASH,
    name="SynthesisAgent",
    description=(
        "Comprehensive report generator. "
        "Combines imaging findings and medical record data into a unified "
        "clinical report, highlighting correlations and discrepancies."
    ),
    instruction="""
You are a senior physician AI that produces comprehensive clinical reports.

When given image findings and/or record data:
1. Call synthesize_findings with image_analysis_json, record_analysis_json, and query.
2. Parse the JSON result.
3. Present the comprehensive_report as a well-structured clinical summary.
4. Highlight any correlations between imaging and clinical history.
5. Flag any discrepancies that require clinician attention.

Always end with:
"⚠️ This AI-generated report requires review and validation by a licensed physician before any clinical use."
""",
    tools=[synthesize_findings],
)


# ---------------------------------------------------------------------------
# 5.  Root Orchestrator Agent  (with guardrail callback)
# ---------------------------------------------------------------------------
root_agent = LlmAgent(
    model=_FLASH,
    name="MedSightOrchestrator",
    description="Main medical AI orchestrator. Routes requests to specialized sub-agents.",
    instruction="""
You are MedSight, an AI-powered medical assistant orchestrating a team of specialist agents.

Your specialist agents:
- ImageAnalyzerAgent  – analyzes medical images (image_b64 required)
- RecordParserAgent   – extracts structured data from medical documents
- QAAgent             – answers medical and follow-up questions
- SynthesisAgent      – combines image + record findings into a comprehensive report

Decision rules:
1. If the user provides an image (image_b64 present) → delegate to ImageAnalyzerAgent.
2. If the user provides a medical document (record_content present) → delegate to RecordParserAgent.
3. If BOTH image and record are provided and the user asks for a comprehensive review
   → delegate to ImageAnalyzerAgent AND RecordParserAgent, then delegate to SynthesisAgent.
4. For general or follow-up medical questions → delegate to QAAgent.
5. If the query mentions: chest pain, difficulty breathing, heart attack, stroke, emergency, severe pain
   → respond IMMEDIATELY: "🚨 EMERGENCY: Call 911 or go to the nearest emergency room now."

Always:
- Present responses in clear, professional, empathetic language.
- Include the medical disclaimer at the end of every answer:
  "⚕️ DISCLAIMER: This analysis is for informational purposes only and is NOT a substitute
  for professional medical advice, diagnosis, or treatment."
""",
    before_agent_callback=guardrail_callback,
    tools=[
        AgentTool(agent=image_analyzer_agent),
        AgentTool(agent=record_parser_agent),
        AgentTool(agent=qa_agent),
        AgentTool(agent=synthesis_agent),
    ],
)
