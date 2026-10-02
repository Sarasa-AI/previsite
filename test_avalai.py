import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# پیدا کردن .env در کنار همین فایل پایتون
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

api_key = os.getenv("AVALAI_API_KEY")

if not api_key:
    raise ValueError(
        f"متغیر AVALAI_API_KEY پیدا نشد. مسیر بررسی‌شده: {env_path}"
    )

client = OpenAI(
    api_key=api_key,
    base_url="https://api.avalai.ir/v1"
)

response = client.chat.completions.create(
    model="gemini-3.5-flash-lite",
    messages=[
        {
            "role": "user",
            "content": "سلام، خودت را در یک جمله معرفی کن."
        }
    ],
    temperature=0.2,
    max_tokens=300
)

print(response.choices[0].message.content)