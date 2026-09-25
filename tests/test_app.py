import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from streamlit.testing.v1 import AppTest

from app import IMAGE_MODEL, Package, design_thumbnail, generate_package, generate_thumbnail


class FakeModels:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class AppTests(unittest.TestCase):
    def test_fresh_start_and_missing_key_message(self):
        app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py")).run()
        self.assertEqual(len(app.exception), 0)
        app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertIn("Enter a Gemini API key", app.error[0].value)

    def test_generated_package_is_visible_in_the_app(self):
        payload = {
            "titles": ["C++ Basics"],
            "description": "A beginner guide.",
            "hashtags": ["#Cpp"],
            "tags": ["C++ tutorial"],
            "script": [{"timestamp": "0:00", "visual_cue": "Code editor", "narration": "Let's begin."}],
            "thumbnail_prompt": "C++ code on a bright screen",
        }
        models = FakeModels(SimpleNamespace(text=json.dumps(payload)))
        with patch("google.genai.Client", return_value=SimpleNamespace(models=models)):
            app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py")).run()
            app.text_input[0].set_value("test-key")
            app.text_input[1].set_value("C++")
            app.button[0].click().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.tabs), 4)
        self.assertTrue(any("#Cpp" in block.value for block in app.code))

    def test_package_has_separate_hashtags_and_schema(self):
        payload = {
            "titles": ["C++ Basics"],
            "description": "A beginner guide.",
            "hashtags": ["Cpp", "#Programming"],
            "tags": ["C++ tutorial"],
            "script": [{"timestamp": "0:00", "visual_cue": "Code editor", "narration": "Let's begin."}],
            "thumbnail_prompt": "C++ code on a bright screen",
        }
        models = FakeModels(SimpleNamespace(text=json.dumps(payload)))
        package, model = generate_package(
            SimpleNamespace(models=models), "Topic: C++", "gemini-3.5-flash-lite"
        )
        self.assertIsInstance(package, Package)
        self.assertEqual(package.hashtags, ["#Cpp", "#Programming"])
        self.assertEqual(model, "gemini-3.5-flash-lite")
        self.assertEqual(models.calls[0]["config"].response_schema, Package)

    def test_thumbnail_is_downloadable_youtube_size(self):
        source = io.BytesIO()
        Image.new("RGB", (320, 180), "blue").save(source, format="PNG")
        part = SimpleNamespace(inline_data=SimpleNamespace(data=source.getvalue()))
        models = FakeModels(SimpleNamespace(parts=[part]))
        thumbnail = generate_thumbnail(SimpleNamespace(models=models), "Blue science graphic")
        with Image.open(io.BytesIO(thumbnail)) as image:
            self.assertEqual(image.size, (1280, 720))
            self.assertEqual(image.format, "JPEG")
        self.assertEqual(models.calls[0]["model"], IMAGE_MODEL)

    def test_quota_fallback_is_downloadable_youtube_size(self):
        thumbnail = design_thumbnail("Python basics for beginners")
        with Image.open(io.BytesIO(thumbnail)) as image:
            self.assertEqual(image.size, (1280, 720))
            self.assertEqual(image.format, "JPEG")


if __name__ == "__main__":
    unittest.main()
