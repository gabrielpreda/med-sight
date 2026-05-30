"""
Medical Tools for MedSight ADK Sub-Agents

Each function is a pure Python tool registered to a specific LlmAgent.
Vertex AI credentials are resolved once at module import time from the
USE_VERTEX_AI / PROJECT_ID / REGION / ENDPOINT_* variables in .env.
"""

import base64
import json
import logging
import os
import re
import requests
import httpx
from io import BytesIO
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# One-time Vertex AI / ADK backend configuration
# ---------------------------------------------------------------------------

def _configure_backend() -> None:
    """
    Translate USE_VERTEX_AI + PROJECT_ID + REGION into the environment
    variables that the google-genai SDK (used by ADK) expects.

    Must be called before any agent or tool uses the genai SDK.
    """
    use_vertexai = os.getenv("USE_VERTEX_AI", "").strip().upper() in ("TRUE", "1", "YES")

    if use_vertexai:
        project  = os.getenv("PROJECT_ID", "")
        location = os.getenv("REGION", "us-central1")

        # Variables consumed by google-genai / ADK
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT",      project)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION",     location)

        # Also initialise the vertexai SDK used by the MedGemma endpoint tool
        try:
            import vertexai
            vertexai.init(project=project, location=location)
        except Exception as exc:
            logger.warning("vertexai.init skipped: %s", exc)

        logger.info(
            "Backend: Vertex AI  project=%s  location=%s", project, location
        )
    else:
        api_key = os.getenv("GOOGLE_API_KEY", "")
        if api_key:
            os.environ.setdefault("GOOGLE_API_KEY", api_key)
        logger.info("Backend: Google AI API (api_key)")


_configure_backend()


# ---------------------------------------------------------------------------
# Helper – Vertex AI dedicated endpoint (MedGemma)
# ---------------------------------------------------------------------------

def _get_medgemma_endpoint():
    """Return the Vertex AI Endpoint object for MedGemma."""
    from google.cloud import aiplatform  # noqa

    project   = os.environ["GOOGLE_CLOUD_PROJECT"]
    location  = os.environ["GOOGLE_CLOUD_LOCATION"]
    ep_id     = os.environ.get("ENDPOINT_ID", "")
    ep_region = os.environ.get("ENDPOINT_REGION", location)

    aiplatform.init(project=project, location=ep_region)
    return aiplatform.Endpoint(
        endpoint_name=ep_id,
        project=project,
        location=ep_region,
    )


def _clean_json(text: str) -> str:
    """Strip markdown code fences that models sometimes emit."""
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*",     "", text)
    text = re.sub(r"\s*```$",     "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Guardrail  –  Medical relevance classifier
# ---------------------------------------------------------------------------

# Topics that are firmly outside evidence-based medicine
_PSEUDOMEDICINE_KEYWORDS = {
    "homeopathy", "homeopathic", "crystal healing", "crystal therapy",
    "astrology", "astrology cure", "aura reading", "aura cleansing",
    "chakra healing", "chakra balancing", "reiki", "energy healing",
    "essential oils cure", "detox tea", "detox cleanse", "alkaline water cure",
    "miracle cure", "colloidal silver", "ear candling", "reflexology cure",
    "magnet therapy", "iridology", "naturopathic cure", "cupping therapy",
    "bloodletting", "urine therapy", "anti-vaccine", "vaccine causes autism",
    "antivax", "ivermectin covid", "hydroxychloroquine covid",
    "bleach cure", "mms therapy", "ozone therapy", "coffee enema",
    "psychic healing", "faith healing", "prayer healing disease",
    "biofield therapy", "quantum healing", "distance healing",
    "herbal cure cancer", "baking soda cancer cure",
}

# Topics entirely outside the medical domain
_NON_MEDICAL_KEYWORDS = {
    "stock price", "lottery numbers", "sports score", "weather forecast",
    "recipe", "cooking", "travel", "vacation", "hotel", "flight",
    "movie", "music", "song lyrics", "book recommendation",
    "write code", "debug code", "programming", "javascript",
    "politics", "election", "government", "military",
    "relationship advice", "dating", "love advice",
    "real estate", "investment advice", "cryptocurrency",
    "joke", "tell me a joke", "game", "play a game",
}


def check_medical_relevance(query: str) -> str:
    """
    Guardrail classifier: determines whether a user query is within the scope
    of evidence-based medicine.

    Layer 1 – fast keyword blocklist (no LLM needed).
    Layer 2 – LLM classification for ambiguous queries.

    Args:
        query: The raw user query string.

    Returns:
        JSON string with keys:
          - verdict: "MEDICAL" | "PSEUDOMEDICINE" | "NON_MEDICAL"
          - reason:  short explanation (shown to the user on rejection)
          - allowed: true | false
    """
    q_lower = query.lower()

    # --- Layer 1: keyword pre-check (fast path) ---
    for kw in _PSEUDOMEDICINE_KEYWORDS:
        if kw in q_lower:
            return json.dumps({
                "verdict": "PSEUDOMEDICINE",
                "reason": (
                    f"Your query appears to be about '{kw}', which is not supported "
                    "by scientific evidence. MedSight only provides evidence-based "
                    "medical information."
                ),
                "allowed": False,
            })

    for kw in _NON_MEDICAL_KEYWORDS:
        if kw in q_lower:
            return json.dumps({
                "verdict": "NON_MEDICAL",
                "reason": (
                    f"Your query seems to be about '{kw}', which is outside MedSight's "
                    "scope. I can only assist with medical images, clinical records, "
                    "and evidence-based health questions."
                ),
                "allowed": False,
            })

    # --- Layer 2: LLM classification (ambiguous queries) ---
    try:
        from google import genai  # noqa

        client = genai.Client()
        prompt = f"""
You are a medical content classifier. Classify the user query below into exactly one category:

MEDICAL        – about human health, anatomy, diseases, medications, medical procedures,
                 medical imaging, laboratory values, or clinical care.
PSEUDOMEDICINE – promotes unscientific, disproven, or harmful treatments or beliefs
                 (homeopathy, crystal healing, anti-vaccine, miracle cures, etc.).
NON_MEDICAL    – completely unrelated to medicine (recipes, sports, politics, code, etc.).

Return ONLY valid JSON, no markdown:
{{
  "verdict": "MEDICAL" | "PSEUDOMEDICINE" | "NON_MEDICAL",
  "reason": "One short sentence explanation"
}}

User query: "{query[:500]}"
"""
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        if resp.text:
            data = json.loads(resp.text.strip())
            verdict = data.get("verdict", "MEDICAL").upper()
            reason  = data.get("reason", "")
            return json.dumps({
                "verdict": verdict,
                "reason":  reason,
                "allowed": verdict == "MEDICAL",
            })
    except Exception as exc:
        logger.warning("Guardrail LLM check failed, defaulting to MEDICAL: %s", exc)

    # Default: allow (fail-open to avoid blocking legitimate queries)
    return json.dumps({"verdict": "MEDICAL", "reason": "", "allowed": True})


# ---------------------------------------------------------------------------
# Tool 1  –  Medical image analysis  (MedGemma dedicated endpoint)
# ---------------------------------------------------------------------------
def is_valid_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, TypeError):
        return False

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "medgemma1.5:4b"  # or medgemma:27b


def analyze_medical_image(
    image_b64: str,
    image_type: str = "unknown",
    query: str = "Analyze this medical image and provide detailed findings.",
    provider: str = "ollama",
) -> str:
    """
    provider:
      - "gcp"    -> current Vertex AI / Model Garden endpoint
      - "ollama" -> local Ollama endpoint
    """
    logger.warning("ADK TOOL SELECTED: analyze_medical_image")

    system_prompt = f"""
        You are a highly experienced medical imaging AI assisting radiologists.

        Analyze the provided {image_type} image and produce a clear, clinically useful report.
        Focus on:
        - Visible anatomical structures
        - Abnormalities, masses, infiltrates, fractures, fluid collections
        - Whether the scan appears normal or requires further evaluation

        Rules:
        - Return VALID JSON ONLY – no markdown, no code fences, no extra text.
        - Use this exact structure:

        {{
        "summary": "2-3 sentence overview",
        "anatomical_structures": ["structure 1"],
        "findings": [{{"finding": "Observation 1"}}],
        "abnormalities": [{{"description": "Abnormality 1"}}],
        "impression": "Clinical impression",
        "recommendations": ["Recommendation 1"],
        "image_quality": {{"assessed": true, "quality": "good"}}
        }}
    """

    try:
        provider = provider.lower().strip()
        print(f"Provider: {provider}")

        if provider == "gcp":
            raw = _call_medgemma_gcp(
                image_b64=image_b64,
                system_prompt=system_prompt,
                query=query,
            )

        elif provider == "ollama":
            raw =  _call_medgemma_ollama(
                image_b64=image_b64,
                system_prompt=system_prompt,
                query=query,
            )

        else:
            raise ValueError("Invalid provider. Use 'gcp' or 'ollama'.")

        print(f"Raw response from {provider}: {raw}")

        cleaned = _clean_json(raw)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            data = json.loads(match.group(0)) if match else {"summary": cleaned}

        return json.dumps(data)

    except Exception as exc:
        logger.error("analyze_medical_image failed: %s", exc, exc_info=True)
        return json.dumps({
            "error": str(exc),
            "summary": "Image analysis failed."
        })


def _call_medgemma_gcp(
    image_b64: str,
    system_prompt: str,
    query: str,
) -> str:
    endpoint = _get_medgemma_endpoint()
    data_url = f"data:image/png;base64,{image_b64}"

    instances = [
        {
            "@requestFormat": "chatCompletions",
            "messages": [
                {
                    "role": "system",
                    "content": [{"type": "text", "text": system_prompt}],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                },
            ],
            "max_tokens": 2500,
            "temperature": 0.0,
        }
    ]


    response = endpoint.predict(
        instances=instances,
        use_dedicated_endpoint=True,
    )

    pred = response.predictions

    if isinstance(pred, dict) and "choices" in pred:
        return pred["choices"][0]["message"]["content"]

    if isinstance(pred, str):
        return pred

    return str(pred)


def _call_medgemma_ollama(
    image_b64: str,
    system_prompt: str,
    query: str,
) -> str:
    print("========================")
    print(f"Query: {query}")
    print("========================")
    logger.warning("ADK TOOL SELECTED: _call_medgemma_ollama")
    logger.warning(f"Query: {query}")

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": query,
                "images": [image_b64],
            },
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "num_predict": 2500,
        },
    }

    # timeout = httpx.Timeout(connect=5.0, read=300.0, write=30.0, pool=5.0)
    # async with httpx.AsyncClient(timeout=timeout) as client:
    #     response = await client.post(OLLAMA_URL, json=payload)

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=150,
    )
    response.raise_for_status()
    print("========================")
    print(f"Response: {response}")
    print("========================")

    return response.json()["message"]["content"]

# ---------------------------------------------------------------------------
# Tool 2  –  Medical record parsing  (Gemini + regex)
# ---------------------------------------------------------------------------

def parse_medical_record(content: str) -> str:
    """
    Extract structured medical information from a clinical document.

    Uses Gemini Flash Lite for deep interpretation and regex for explicit
    headers and dates.

    Args:
        content: Raw text of the medical record (first 10 000 chars used).

    Returns:
        JSON string with keys: diagnoses, medications, procedures,
        dates, summary, analysis_notes, critical_flags.
        On failure returns JSON with an 'error' key.
    """
    # --- Regex extraction ---
    def _rx(pattern, text):
        return list({
            m.group(1).strip()
            for m in re.finditer(pattern, text, re.I)
            if 3 <= len(m.group(1).strip()) <= 100
        })

    diagnoses_rx  = _rx(r'(?:diagnosis|impression|assessment):\s*([^\n\.]+)', content)
    diagnoses_rx += _rx(r'\bdiagnosed with\s+([a-z\s]+)(?:,|\.|and)', content)
    meds_rx       = _rx(r'(?:medication|prescribed|rx|treatment):\s*([^\n\.]+)', content)
    procs_rx      = _rx(r'(?:procedure|surgery|operation|plan):\s*([^\n\.]+)', content)
    dates_rx      = list({
        m.group(1)
        for m in re.finditer(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', content)
    })

    # --- LLM extraction ---
    llm_data: dict = {}
    try:
        from google import genai  # noqa

        client = genai.Client()
        prompt = f"""
You are an expert medical AI. Analyze the clinical document below and return ONLY valid JSON.

TEXT:
{content[:10000]}

OUTPUT FORMAT (JSON only, no markdown):
{{
  "diagnoses":      ["confirmed diagnosis 1"],
  "medications":    ["medication 1"],
  "procedures":     ["procedure 1"],
  "summary":        "Professional 2-3 sentence summary of key findings",
  "critical_flags": ["any critical red flags"],
  "analysis_notes": "Other relevant observations"
}}
"""
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        if resp.text:
            llm_data = json.loads(resp.text)
    except Exception as exc:
        logger.warning("LLM record parsing fell back to regex only: %s", exc)

    # Merge regex + LLM
    all_diag  = list(set(diagnoses_rx + llm_data.get("diagnoses",  [])))
    all_meds  = list(set(meds_rx      + llm_data.get("medications", [])))
    all_procs = list(set(procs_rx     + llm_data.get("procedures",  [])))

    summary = llm_data.get("summary") or " | ".join(filter(None, [
        f"Diagnoses: {', '.join(all_diag[:5])}"   if all_diag  else "",
        f"Medications: {', '.join(all_meds[:5])}" if all_meds  else "",
        f"Procedures: {', '.join(all_procs[:5])}" if all_procs else "",
    ])) or "No structured information extracted."

    return json.dumps({
        "diagnoses":      all_diag,
        "medications":    all_meds,
        "procedures":     all_procs,
        "dates":          dates_rx,
        "summary":        summary,
        "analysis_notes": llm_data.get("analysis_notes", ""),
        "critical_flags": llm_data.get("critical_flags", []),
    })


# ---------------------------------------------------------------------------
# Tool 3  –  Medical QA  (conversation context retrieval)
# ---------------------------------------------------------------------------

def answer_medical_question(
    query: str,
    conversation_history_json: str = "[]",
) -> str:
    """
    Answer a general medical or follow-up question using conversation context.

    Args:
        query: The user's question.
        conversation_history_json: JSON array of past chat messages
            [{"role": "user"|"assistant", "content": "..."}].

    Returns:
        JSON string with key 'answer'.
    """
    try:
        history = json.loads(conversation_history_json)
    except Exception:
        history = []

    context = "\n".join(
        f"{m.get('role','user').capitalize()}: {m.get('content','')[:300]}"
        for m in history[-3:]
    )

    # Fast-path: known medical term explanations
    explanations = {
        "costophrenic angle": (
            "The costophrenic angle is the sharp corner where the diaphragm meets the "
            "chest wall on X-ray. Sharp angles are normal; blunting suggests pleural effusion."
        ),
        "infiltrate": (
            "An infiltrate is an abnormal substance (fluid, cells) accumulated in lung "
            "tissue, indicating infection, inflammation, or other pathology."
        ),
        "consolidation": (
            "Consolidation means a lung region has filled with liquid instead of air – "
            "appears white on X-ray, commonly seen in pneumonia."
        ),
        "opacity": (
            "Opacity is an area with increased density on imaging, indicating fluid "
            "or solid material instead of normal aerated tissue."
        ),
        "atelectasis": (
            "Atelectasis is partial or complete lung collapse, appearing as increased "
            "density or volume loss on imaging."
        ),
    }

    q_lower = query.lower()
    for term, explanation in explanations.items():
        if term in q_lower:
            if context:
                explanation += f"\n\nIn the context of our discussion:\n{context}"
            return json.dumps({"answer": explanation})

    # Generic response with context
    if context:
        answer = (
            f"Based on our conversation:\n{context}\n\n"
            "For your specific question, please consult a qualified healthcare professional."
        )
    else:
        answer = (
            "I can help with medical questions. Please provide more details or "
            "upload medical images / records for a more specific analysis."
        )
    return json.dumps({"answer": answer})


# ---------------------------------------------------------------------------
# Tool 4  –  Synthesis  (combine image + record findings)
# ---------------------------------------------------------------------------

def synthesize_findings(
    image_analysis_json: str = "{}",
    record_analysis_json: str = "{}",
    query: str = "",
) -> str:
    """
    Produce a comprehensive clinical report by combining imaging and record findings.

    Args:
        image_analysis_json: JSON string returned by the ImageAnalyzerAgent.
        record_analysis_json: JSON string returned by the RecordParserAgent.
        query: Original user question for context.

    Returns:
        JSON string with key 'comprehensive_report'.
    """
    try:
        img = json.loads(image_analysis_json)  if image_analysis_json  else {}
        rec = json.loads(record_analysis_json) if record_analysis_json else {}
    except Exception:
        img, rec = {}, {}

    parts: list[str] = []

    if img.get("summary"):
        parts.append(f"**Imaging Findings:**\n{img['summary']}")

    if rec.get("summary"):
        parts.append(f"**Clinical History:**\n{rec['summary']}")

    # Keyword correlations
    img_str = str(img).lower()
    rec_str = str(rec).lower()
    correlated = [
        t for t in ["pneumonia", "fracture", "mass", "infiltrate", "consolidation"]
        if t in img_str and t in rec_str
    ]
    if correlated:
        parts.append(
            "**Correlated Findings:**\n"
            + "\n".join(
                f"- {t.capitalize()} noted in both imaging and clinical history"
                for t in correlated
            )
        )

    # Discrepancy
    if "normal" in img.get("summary", "").lower() and "abnormal" in rec.get("summary", "").lower():
        parts.append(
            "**⚠️ Discrepancy:**\n"
            "Imaging appears normal but clinical history suggests abnormality. "
            "Clinical correlation is strongly recommended."
        )

    if rec.get("medications"):
        parts.append(
            "**Note:** Current medications should be considered when interpreting imaging findings."
        )

    report = "\n\n".join(parts) if parts else "Insufficient data for comprehensive synthesis."
    return json.dumps({"comprehensive_report": report})
