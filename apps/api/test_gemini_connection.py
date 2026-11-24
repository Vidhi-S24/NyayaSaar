
from app.config import get_settings
from google import genai
from google.genai import types

settings = get_settings()
client = genai.Client(api_key=settings.ai_api_key)

print("Testing Gemini structured JSON...")
print("Model:", settings.ai_model)

response = client.models.generate_content(
    model=settings.ai_model,
    contents='Return {"status": "ok"}',
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema={
            "type": "OBJECT",
            "properties": {
                "status": {"type": "STRING"}
            },
            "required": ["status"],
        },
    ),
)

print("Response:", response.text)
print("Structured JSON test successful!")
