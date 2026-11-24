
from app.config import get_settings
from google import genai

settings = get_settings()
client = genai.Client(api_key=settings.ai_api_key)

model = "gemini-3.8-flash"

print("Testing basic Gemini generation...")
print("Model:", model)

response = client.models.generate_content(
    model=model,
    contents="Reply with exactly: GEMINI_OK",
)

print("Response:", response.text)
print("Basic generation successful!")
