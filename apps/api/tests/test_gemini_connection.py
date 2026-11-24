
from app.config import get_settings
from google import genai

settings = get_settings()

assert settings.ai_api_key, "API key missing"

client = genai.Client(api_key=settings.ai_api_key)

print("Model:", settings.ai_model)

response = client.models.generate_content(
    model=settings.ai_model,
    contents="Reply with exactly GEMINI_OK",
)

print("Response:", response.text)
