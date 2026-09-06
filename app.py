import streamlit as st
from groq import Groq
import json
import urllib.parse

st.set_page_config(page_title="AI YouTube Creator", page_icon="🎬", layout="wide")

st.title("🎬 YouTube Content Studio AI")
st.caption("Generate complete video packages powered by Groq (Llama 3.1 8B).")

# Checks for either GROQ_API_KEY or GEMINI_API_KEY from Secrets
groq_api_key = st.secrets.get("GROQ_API_KEY") or st.secrets.get("GEMINI_API_KEY", None)

with st.sidebar:
    st.header("Configuration")
    if not groq_api_key:
        groq_api_key = st.text_input("Groq API Key", type="password")
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
  "thumbnail_prompt": "A detailed visual description for an AI image generator (vibrant lighting, expressive subject, high resolution, no text)."
}
"""

if generate_btn:
    if not groq_api_key:
        st.error("Please provide a Groq API Key in the sidebar or via Streamlit Secrets.")
    elif not topic:
        st.error("Please provide a video topic.")
    else:
        with st.spinner("Generating script and thumbnail with Groq..."):
            try:
                client = Groq(api_key=groq_api_key)
                user_prompt = f"Create a full package for a video about '{topic}'. Audience: {target_audience}. Tone: {tone}. Target duration: {duration}."
                
                chat_completion = client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    model="llama-3.1-8b-instant",
                    response_format={"type": "json_object"},
                    temperature=0.7,
                )
                
                response_text = chat_completion.choices[0].message.content
                data = json.loads(response_text)
                
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
                    st.subheader("Generated Thumbnail Concept")
                    t_prompt = data.get("thumbnail_prompt", "")
                    st.write(f"**Image Prompt:** _{t_prompt}_")
                    
                    encoded_prompt = urllib.parse.quote(t_prompt)
                    thumbnail_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1280&height=720&nologo=true"
                    st.image(thumbnail_url, caption="Generated via Pollinations.ai (1280x720)", use_container_width=True)
                    
            except Exception as e:
                st.error(f"Execution Error: {e}")
