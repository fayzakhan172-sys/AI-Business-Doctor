import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

# Model name can be changed from .env (GEMINI_MODEL=...)
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


def ask_llm(prompt, retries=3):
    """Send a prompt to Gemini and return the answer as text.
    Fails after 30 seconds instead of hanging; retries if busy (503/429)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not found. Check your .env file.")

    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=30000),  # 30 seconds
    )

    for attempt in range(retries):
        try:
            response = client.models.generate_content(model=MODEL, contents=prompt)
            return response.text
        except errors.APIError as e:
            busy = getattr(e, "code", None) in (429, 503)
            if busy and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise