import os
import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GAPGPT_API_KEY")
base_url = os.getenv("GAPGPT_BASE_URL", "https://api.gapgpt.app/v1")
model = os.getenv("GAPGPT_MODEL", "gapgpt-qwen-3.5")

client = OpenAI(
    base_url=base_url,
    api_key=api_key,
    http_client=httpx.Client()
)

print(f"Testing GapGPT API with base_url: {base_url}")
print(f"Model: {model}")
print("-" * 50)

try:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "سلام!"}]
    )
    print("Test successful!")
    print(f"Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"Test failed with error: {e}")
