
import streamlit as st
from io import StringIO
from dotenv import load_dotenv

import os

from google.cloud import aiplatform
import base64


from io import BytesIO
from PIL import Image



st.set_page_config(page_title='MedSight', 
                    page_icon = "images/gemini_avatar.png",
                    initial_sidebar_state = 'auto')

@st.cache_resource
def initialize_model():
    """
    Configure the Google generativeai with the GEMINI_API_KEY
    """
    load_dotenv()

    PROJECT_ID = os.getenv("PROJECT_ID")
    REGION = os.getenv("REGION")
    ENDPOINT_ID = os.getenv("ENDPOINT_ID")
    ENDPOINT_REGION = os.getenv("ENDPOINT_REGION")

    print("Initializing Vertex AI API.")
    aiplatform.init(project=PROJECT_ID, location=REGION)

    endpoints = {}

    endpoints["endpoint"] = aiplatform.Endpoint(
        endpoint_name=ENDPOINT_ID,
        project=PROJECT_ID,
        location=ENDPOINT_REGION,
    )

    endpoint = endpoints["endpoint"]

    return endpoint


endpoint = initialize_model()
use_dedicated_endpoint = True

avatars = {
    "assistant" : "images/gemini_avatar.png",
    "user": "images/user_avatar.png"
}

st.markdown("<h2 style='text-align: center; color: #3184a0;'>MedSight Chatbot</h2>", unsafe_allow_html=True)

with st.sidebar:
    st.image("images/gemini_avatar.png")

if "messages" not in st.session_state.keys():
    st.session_state.messages = [
        {"role": "assistant", "content": "How may I assist you today?", "image": None}
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"], 
                         avatar=avatars[message["role"]]):
        st.write(message["content"])
        if message["role"] == "assistant" and message["image"]:
            st.image(message["image"])


def clear_chat_history():
    st.session_state.messages = [
        {"role": "assistant", "content": "How may I assist you today?"}
    ]
    
st.sidebar.button("Clear Chat History", on_click=clear_chat_history)
with st.sidebar:
    uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])

    if uploaded_file:
        # Load with PIL the uploaded image
        image =Image.open(uploaded_file)

        # Convert to base64 and build a data URL
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_bytes = buffered.getvalue()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
       
        # We store the uploaded image (transformed with b64) to be used in the model prompt
        if "img_b64" not in st.session_state:
            st.session_state.img_b64 = img_b64

        # The image is displayed using the initial PIL format
        st.image(image, caption="Uploaded Image", use_column_width=True)


def run_query(input_text, 
              max_tokens=500,
              temperature=0, 
              raw_response=True):
    """
    Run query. The model is initialized and then queried.
    Args:
        input_text (str): We are passing to the model the user prompt
        max_toxens (int): Max number of tokens in the output
        temperature (float): Should be allways 0
        raw_response (boolean): Set it to True
    Returns:
        prediction (str): the text of the response
    """
    try:
        # Set system prompt
        system_instruction = """
            You are a highly experienced and accurate medical imaging AI, trained to assist radiologists in interpreting 
            diagnostic images.

            You are analyzing an input medical image, referred to as "the scan". Your role is to generate a clear, 
            clinically useful description of the scan, identifying relevant anatomical structures, patterns, 
            anomalies, and potential diagnoses. Do not guess or hallucinate findings not evident in the image.

            Focus on:
            - Location and characteristics of any visible abnormalities
            - Indicators of common pathologies (e.g., fractures, infiltrates, masses)
            - Whether the image appears normal or requires further evaluation

            Use formal, clinical language and do not include disclaimers unless findings are uncertain. 
            If the image quality is too poor to analyze, state this clearly.

            Your response should begin with a short summary, followed by a more detailed paragraph when appropriate.
        """

        # Set user prompt
        prompt = input_text

        # Set image data (data_url)
        img_b64 = st.session_state.img_b64
        data_url = f"data:image/png;base64,{img_b64}"


        formatted_prompt = f"{system_instruction} {prompt} <start_of_image>"

        instances = [
            {
                "prompt": formatted_prompt,
                "multi_modal_data": {"image":data_url},
                "max_tokens": max_tokens,
                "temperature": temperature,
                "raw_response": raw_response,
            }
        ]

        response = endpoint.predict(
            instances=instances, use_dedicated_endpoint=use_dedicated_endpoint
        )
        prediction = response.predictions[0]

        if prediction:
            return prediction
        
        else:
            return "Error"

    except Exception as ex:
        print(f"Exception: {ex}")
        return "Error"
    

output = st.empty()
if prompt := st.chat_input():
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=avatars["user"]):
        st.write(prompt)

if st.session_state.messages[-1]["role"] != "assistant":
    with st.chat_message("assistant", avatar=avatars["assistant"]):
        with st.spinner("Thinking..."):
            

            response = run_query(prompt, max_tokens=128)
            placeholder = st.empty()
            full_response = response

            placeholder.markdown(full_response, unsafe_allow_html=True)
            placeholder.markdown(response, unsafe_allow_html=True)

    message = {
                "role": "assistant", 
                "content": response,
                "avatar": avatars["assistant"]
               }
    st.session_state.messages.append(message)