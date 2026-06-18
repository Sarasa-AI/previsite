import asyncio
import httpx
from openai import AsyncOpenAI

# کلید API ارائه شده شما برای OpenRouter
OPENROUTER_API_KEY = "your-openrouter-api-key"

async def test_api_connection():
    print("Initializing AsyncOpenAI client for OpenRouter...")
    
    # تنظیم کلاینت منطبق بر بیس‌یو‌آر‌ال OpenRouter
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        http_client=httpx.AsyncClient(timeout=30.0)
    )

    # پرامپت تستی بالینی برای ارزیابی توانایی مدل در تفکیک ساختار دینامیک (HPI)
    system_prompt = (
        "You are a medical AI assistant. Your job is to analyze the user's chief complaint "
        "and return a valid JSON object containing exactly two context-aware HPI questions."
    )
    user_message = "I am a 28-year-old male experiencing sudden, sharp chest pain for the past 2 hours."

    print("Sending request to OpenRouter (Model: qwen/qwen-2.5-72b-instruct)...")
    try:
        response = await client.chat.completions.create(
            model="qwen/qwen-2.5-72b-instruct", # یک مدل بهینه و در دسترس در OpenRouter
            temperature=0.1,
            response_format={"type": "json_object"}, # فعال‌سازی حالت اجبار به خروجی JSON
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
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
    # اجرای حلقه ناهمگام پایتون
    asyncio.run(test_api_connection())