"""AI YouTube content package generator."""

from __future__ import annotations

import io
import os

import streamlit as st
from google import genai
from google.genai import types
from google.genai.errors import APIError
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, ValidationError
from streamlit.errors import StreamlitSecretNotFoundError

TEXT_MODELS = ("gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash")
IMAGE_MODEL = "gemini-3.1-flash-lite-image"


class Scene(BaseModel):
    timestamp: str
    visual_cue: str
    narration: str


class Package(BaseModel):
    titles: list[str]
    description: str
    hashtags: list[str]
    tags: list[str]
    script: list[Scene]
    thumbnail_prompt: str


SYSTEM_PROMPT = """
You are an expert YouTube content strategist and scriptwriter.
Create a useful, accurate package for the requested topic, audience, tone, and
duration. Include five distinct titles, a publishable description, 5-10
hashtags beginning with #, 8-15 plain search tags, and a scene-by-scene script
with spoken narration and visual cues. Make the narration long enough for the
requested duration. Write a thumbnail prompt with a clear subject, strong
contrast, and 16:9 composition. Avoid misleading claims and invented facts.
"""


def saved_api_key() -> str:
    """Read a configured key even when secrets.toml does not exist."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    try:
        return str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    except StreamlitSecretNotFoundError:
        return ""


def validate_package(package: Package) -> Package:
    if (
        not package.titles
        or not package.description.strip()
        or not package.hashtags
        or not package.script
        or not package.thumbnail_prompt.strip()
    ):
        raise ValueError("The model returned an incomplete package. Please try again.")
    if any(not value.strip() for value in package.titles + package.hashtags):
        raise ValueError("The model returned blank titles or hashtags. Please try again.")
    if any(not scene.narration.strip() for scene in package.script):
        raise ValueError("The model returned an incomplete script. Please try again.")
    package.hashtags = ["#" + tag.lstrip("#") for tag in package.hashtags]
    return package


def generate_package(client, prompt: str, preferred_model: str) -> tuple[Package, str]:
    models = (preferred_model, *(m for m in TEXT_MODELS if m != preferred_model))
    last_error = None
    for model in models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=Package,
                    temperature=0.7,
                ),
            )
            if not response.text:
                raise ValueError("The model returned no text. Please try again.")
            return validate_package(Package.model_validate_json(response.text)), model
        except APIError as exc:
            last_error = exc
            # A missing or unavailable model can be retried with another model.
            if getattr(exc, "code", None) not in (404, 503):
                raise
    raise last_error or RuntimeError("No text model was available.")


def generate_thumbnail(client, prompt: str) -> bytes:
    response = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=f"Create a YouTube thumbnail image. {prompt}. No text or logos.",
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="16:9", image_size="1K"),
        ),
    )
    for part in response.parts or []:
        if part.inline_data and part.inline_data.data:
            image = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
            image = ImageOps.fit(image, (1280, 720), method=Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=88, optimize=True)
            return output.getvalue()
    raise ValueError("The image model returned no image. Try another prompt.")


def design_thumbnail(title: str) -> bytes:
    """Create a readable 16:9 thumbnail when image API quota is unavailable."""
    image = Image.new("RGB", (1280, 720))
    draw = ImageDraw.Draw(image)
    for y in range(720):
        draw.line((0, y, 1280, y), fill=(10 + y // 80, 21 + y // 42, 45 + y // 25))
    draw.ellipse((830, -250, 1450, 370), fill=(17, 102, 146))
    draw.ellipse((940, 320, 1400, 780), fill=(27, 67, 130))
    draw.rounded_rectangle((75, 74, 320, 130), radius=20, fill=(255, 203, 57))

    def font(size: int):
        for name in ("DejaVuSans-Bold.ttf", "arialbd.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                pass
        return ImageFont.load_default()

    draw.text((98, 89), "NEW VIDEO", font=font(28), fill=(18, 28, 54))
    words = title.strip().split() or ["YOUR VIDEO"]
    for size in range(100, 43, -4):
        title_font = font(size)
        lines = []
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if line and draw.textbbox((0, 0), candidate, font=title_font)[2] > 1030:
                lines.append(line)
                line = word
            else:
                line = candidate
        lines.append(line)
        if len(lines) <= 4 and len(lines) * (size + 16) <= 435:
            break
    y = 174
    for line in lines:
        draw.text((73, y + 5), line, font=title_font, fill=(0, 0, 0), stroke_width=4, stroke_fill=(0, 0, 0))
        draw.text((73, y), line, font=title_font, fill="white", stroke_width=2, stroke_fill=(18, 28, 54))
        y += size + 16
    draw.rounded_rectangle((75, 636, 575, 649), radius=6, fill=(255, 203, 57))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=88, optimize=True)
    return output.getvalue()


def script_text(package: Package) -> str:
    return "\n\n".join(
        f"{scene.timestamp}\nVisual: {scene.visual_cue}\nNarration: {scene.narration}"
        for scene in package.script
    )


def main() -> None:
    st.set_page_config(page_title="AI YouTube Creator", page_icon="🎬", layout="wide")
    st.title("🎬 YouTube Content Studio AI")
    st.caption("Generate scripts, titles, descriptions, hashtags, and a downloadable thumbnail.")

    api_key = saved_api_key()
    with st.sidebar:
        st.header("Configuration")
        if api_key:
            st.caption("Gemini API key loaded from configuration.")
        else:
            api_key = st.text_input("Gemini API Key", type="password")
        topic = st.text_input("Video Topic / Keyword", placeholder="e.g., How to Learn C++")
        audience = st.text_input("Target Audience", placeholder="e.g., CS beginners")
        tone = st.selectbox(
            "Tone",
            ["Fast-paced & Engaging", "Documentary & Serious", "Humorous & Punchy", "Step-by-Step Educational"],
        )
        duration = st.selectbox("Target Duration", ["Shorts / Under 60s", "3 - 5 Minutes", "8 - 10 Minutes"])
        preferred_model = st.selectbox("Text Model", TEXT_MODELS)
        generate = st.button("Generate Package", type="primary", use_container_width=True)

    if generate:
        if not api_key.strip():
            st.error("Enter a Gemini API key to generate content.")
        elif not topic.strip():
            st.error("Enter a video topic.")
        else:
            prompt = (
                f"Topic: {topic.strip()}\nAudience: {audience.strip() or 'General viewers'}\n"
                f"Tone: {tone}\nTarget duration: {duration}"
            )
            try:
                with st.spinner("Generating your content package..."):
                    package, model = generate_package(genai.Client(api_key=api_key.strip()), prompt, preferred_model)
                st.session_state["package"] = package.model_dump()
                st.session_state["used_model"] = model
                st.session_state["thumbnail_bytes"] = None
                st.session_state["thumbnail_prompt_input"] = package.thumbnail_prompt
            except (APIError, ValidationError, ValueError) as exc:
                st.error(f"Content generation failed: {exc}")

    if "package" not in st.session_state:
        return

    package = Package.model_validate(st.session_state["package"])
    st.success(f"Content generated with {st.session_state['used_model']}.")
    titles_tab, script_tab, description_tab, thumbnail_tab = st.tabs(
        ["Titles & Tags", "Script", "Description & Hashtags", "Thumbnail"]
    )

    with titles_tab:
        st.subheader("Title ideas")
        for index, title in enumerate(package.titles, 1):
            st.write(f"{index}. {title}")
        st.subheader("Search tags")
        st.code(", ".join(package.tags))

    with script_tab:
        st.subheader("Scene-by-scene script")
        for scene in package.script:
            with st.expander(scene.timestamp):
                st.write(f"**Visual:** {scene.visual_cue}")
                st.write(f"**Narration:** {scene.narration}")
        st.download_button("Download script", script_text(package), "script.txt", "text/plain")

    with description_tab:
        st.subheader("Video description")
        st.code(package.description)
        st.subheader("Hashtags")
        st.code(" ".join(package.hashtags))
        st.download_button(
            "Download description and hashtags",
            package.description + "\n\n" + " ".join(package.hashtags),
            "description.txt",
            "text/plain",
        )

    with thumbnail_tab:
        st.subheader("Thumbnail")
        st.text_input("Thumbnail visual prompt", key="thumbnail_prompt_input")
        if st.button("Generate thumbnail"):
            image_prompt = st.session_state["thumbnail_prompt_input"].strip()
            if not image_prompt:
                st.error("Enter a thumbnail prompt.")
            elif not api_key.strip():
                st.error("Enter a Gemini API key to generate the thumbnail.")
            else:
                try:
                    with st.spinner("Generating thumbnail..."):
                        try:
                            st.session_state["thumbnail_bytes"] = generate_thumbnail(
                                genai.Client(api_key=api_key.strip()), image_prompt
                            )
                        except APIError as exc:
                            if getattr(exc, "code", None) not in (403, 404, 429):
                                raise
                            st.session_state["thumbnail_bytes"] = design_thumbnail(package.titles[0])
                            st.warning("Gemini image generation is unavailable for this API key. A designed thumbnail was created instead.")
                except (APIError, ValueError, OSError) as exc:
                    st.error(f"Thumbnail generation failed: {exc}")
        if st.session_state.get("thumbnail_bytes"):
            st.image(st.session_state["thumbnail_bytes"], caption="1280 × 720 thumbnail", use_container_width=True)
            st.download_button(
                "Download thumbnail",
                st.session_state["thumbnail_bytes"],
                "thumbnail.jpg",
                "image/jpeg",
            )

    st.download_button(
        "Download complete package (JSON)",
        package.model_dump_json(indent=2),
        "youtube_package.json",
        "application/json",
    )


if __name__ == "__main__":
    main()
