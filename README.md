# AI YouTube Content Creator

Generate a YouTube content package from a topic: titles, a scene-by-scene
script, a description, hashtags, search tags, and a thumbnail image.

## Run locally

1. Install Python 3.10 or newer.
2. Create an environment and install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Start the app:

   ```powershell
   .\.venv\Scripts\python.exe -m streamlit run app.py
   ```

4. Enter a Gemini API key in the sidebar and provide a video topic. You can
   instead set the `GEMINI_API_KEY` environment variable or put the key in
   `.streamlit/secrets.toml` as `GEMINI_API_KEY = "..." `.

The app calls Gemini once for the text package and separately when you click
**Generate thumbnail**. API availability, quotas, and billing depend on your
Gemini account. If image generation is unavailable, the thumbnail prompt and
all text outputs remain available. No key or generated content is committed.
