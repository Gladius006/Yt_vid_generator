import json
import urllib.parse
import streamlit as st
from google import genai
from google.genai import types
from google.genai.errors import APIError

st.set_page_config(page_title="AI YouTube Creator", page_icon="🎬", layout="wide")

st.title("🎬 YouTube Content Studio AI")
st.caption("Generate complete video packages: titles, descriptions, scripts, and FLUX thumbnails.")

# Check if key is configured in Streamlit Secrets, otherwise fallback to input
gemini_api_key = st.secrets.get("GEMINI_API_KEY", None)

with st.sidebar:
    st.header("Configuration")
    if not gemini_api_key:
        gemini_api_key = st.text_input("Gemini API Key", type="password")
    
    preferred_model = st.selectbox(
        "Preferred Gemini Model",
        ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]
    )
    topic = st.text_input("Video Topic / Keyword", placeholder="e.g., How to Learn C++ in 2026")
    target_audience = st.text_input("Target Audience", placeholder="e.g., Beginners, CS Students")
    tone = st.selectbox("Tone", ["Fast-paced & Engaging", "Documentary & Serious", "Humorous & Punchy", "Step-by-Step Educational"])
    duration = st.selectbox("Target Duration", ["Shorts / Under 60s", "3 - 5 Minutes", "8 - 10 Minutes"])
    generate_btn = st.button("Generate Package", type="primary", use_container_width=True)

SYSTEM_PROMPT = """
You are an expert YouTube content strategist and scriptwriter.
Return ONLY a valid JSON object matching this schema:
{
  "titles": ["Title 1", "Title 2", "Title 3", "Title 4", "Title 5"],
  "description": "Full SEO-optimized description with hashtags.",
  "tags": ["tag1", "tag2", "tag3"],
  "script": [
    {"timestamp": "0:00 - 0:30", "visual_cue": "Description of visuals/b-roll", "narration": "Exact spoken narration."}
  ],
  "thumbnail_prompt": "A direct, keyword-focused visual prompt for an image model. MUST explicitly name the core subject (e.g. 'Minecraft blocky voxel cube world', 'C++ code syntax floating on cyber screen'). Include art style, vivid lighting, sharp focus, 3D render style, 16:9 composition. Keep under 35 words. Do not write full sentences."
}
"""

if generate_btn:
    if not gemini_api_key:
        st.error("Please provide a Gemini API Key in the sidebar or via Streamlit Secrets.")
    elif not topic:
        st.error("Please provide a video topic.")
    else:
        # Fallback sequence using currently active Google models
        all_models = ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]
        fallback_models = [preferred_model] + [m for m in all_models if m != preferred_model]
        
        client = genai.Client(api_key=gemini_api_key.strip())
        user_prompt = f"Create a full package for a video about '{topic}'. Audience: {target_audience}. Tone: {tone}. Target duration: {duration}."
        
        response_text = None
        used_model = None

        with st.spinner("Writing script and generating package..."):
            for model_id in fallback_models:
                try:
                    response = client.models.generate_content(
                        model=model_id,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            response_mime_type="application/json",
                            temperature=0.7
                        )
                    )
                    response_text = response.text
                    used_model = model_id
                    break
                except APIError as e:
                    # Catch overloads (503), deprecations (404), and rate-limits to continue failover
                    err_str = str(e).upper()
                    if any(code in err_str for code in ["503", "404", "UNAVAILABLE", "NOT_FOUND", "RESOURCE_EXHAUSTED"]):
                        st.warning(f"⚠️ `{model_id}` unavailable or overloaded. Trying next backup model...")
                        continue
                    else:
                        st.error(f"API Error on {model_id}: {e}")
                        break
                except Exception as ex:
                    st.error(f"Unexpected Error on {model_id}: {ex}")
                    break

        if response_text:
            try:
                st.session_state["generated_data"] = json.loads(response_text)
                st.session_state["used_model"] = used_model
                st.session_state["topic"] = topic
            except json.JSONDecodeError:
                st.error("Failed to parse structured JSON from model response. Please try again.")

# Display results if available in session state
if "generated_data" in st.session_state:
    data = st.session_state["generated_data"]
    used_model = st.session_state.get("used_model", "Gemini")
    st.success(f"Generated successfully using `{used_model}`")
    
    tab_titles, tab_script, tab_desc, tab_thumb = st.tabs(["📌 Titles & Tags", "📜 Script & B-Roll", "📝 SEO Description", "🖼️ Thumbnail"])
    
    with tab_titles:
        st.subheader("High-CTR Titles")
        for i, t in enumerate(data.get("titles", []), 1):
            st.write(f"**{i}.** {t}")
        st.divider()
        st.subheader("Tags")
        st.code(", ".join(data.get("tags", [])))
        
    with tab_script:
        st.subheader("Scene-by-Scene Script")
        for scene in data.get("script", []):
            with st.expander(f"⏱️ {scene.get('timestamp', 'Scene')}"):
                st.write(f"**Visuals:** _{scene.get('visual_cue')}_")
                st.write(f"**Narration:** {scene.get('narration')}")
                
    with tab_desc:
        st.subheader("SEO Description")
        st.text_area("Copy Description", value=data.get("description", ""), height=250)
        
    with tab_thumb:
        st.subheader("Generated Thumbnail Concept (FLUX Engine)")
        raw_prompt = data.get("thumbnail_prompt", st.session_state.get("topic", ""))
        
        # Interactive prompt editor
        custom_prompt = st.text_input("Thumbnail Visual Prompt (Editable):", value=raw_prompt)
        clean_prompt = custom_prompt.strip().replace("\n", " ")
        encoded_prompt = urllib.parse.quote(clean_prompt)
        
        thumbnail_url = (
            f"https://image.pollinations.ai/prompt/{encoded_prompt}"
            f"?width=1280&height=720&model=flux&nologo=true&enhance=true"
        )
        
        st.image(thumbnail_url, caption="Generated via FLUX on Pollinations.ai (1280x720)", use_container_width=True)
        st.caption("Tip: You can edit the prompt box above and press Enter to adjust the thumbnail.")
