import asyncio
import os

import httpx
from openai import AsyncOpenAI

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


async def test_api_connection():
    if not OPENROUTER_API_KEY.strip():
        print("OPENROUTER_API_KEY is not set. Export it before running this script.")
        return

    print("Initializing AsyncOpenAI client for OpenRouter...")

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        http_client=httpx.AsyncClient(timeout=30.0),
    )

    system_prompt = (
        "You are a medical AI assistant. Your job is to analyze the user's chief complaint "
        "and return a valid JSON object containing exactly two context-aware HPI questions."
    )
    user_message = "I am a 28-year-old male experiencing sudden, sharp chest pain for the past 2 hours."

    print("Sending request to OpenRouter (Model: google/gemini-2.5-flash-lite)...")
    try:
        response = await client.chat.completions.create(
            model="google/gemini-2.5-flash-lite",
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )

        print("\n=== API TEST SUCCESSFUL ===")
        print(f"Provider/Model Used: {response.model}")
        print("LLM Response Content:")
        print(response.choices[0].message.content.strip())
        print("===========================")

    except Exception as e:
        print("\n=== API TEST FAILED ===")
        print(f"An error occurred during runtime execution: {str(e)}")
        print("=======================")


if __name__ == "__main__":
    asyncio.run(test_api_connection())
