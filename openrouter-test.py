import os
import httpx
import asyncio

async def test_openrouter():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ خطا: OPENROUTER_API_KEY پیدا نشد.")
        return

    print("🚀 در حال تلاش برای اتصال به OpenRouter...")
    url = "https://openrouter.ai/api/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                print("✅ اتصال موفقیت‌آمیز بود! (وضعیت 200)")
                models = response.json().get("data", [])
                print(f"تعداد مدل‌های دریافتی: {len(models)}")
            else:
                print(f"❌ خطا در اتصال. کد وضعیت: {response.status_code}")
                print(response.text)
    except Exception as e:
        print(f"❌ خطا در برقراری اتصال شبکه: {e}")

if __name__ == "__main__":
    asyncio.run(test_openrouter())