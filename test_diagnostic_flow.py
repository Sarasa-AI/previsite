import sys
import os
from dotenv import load_dotenv # این خط را اضافه کنید

# اضافه کردن مسیر پوشه backend برای ایمپورت‌ها
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

# بارگذاری متغیرها از فایل .env
load_dotenv(os.path.join(os.path.dirname(__file__), 'backend', '.env'))

from app.services.llm_service import LLMService
# ... بقیه کد
import asyncio
from backend.app.services.llm_service import LLMService
from backend.app.schemas.medical import MedicalSummary

async def run_test():
    print("--- شروع شبیه‌سازی مصاحبه بالینی (تست استدلال تشخیصی) ---")
    
    # نمونه‌سازی از سرویس
    llm_service = LLMService()
    
    chat_history = [
        {"role": "system", "content": "تو یک پزشک متخصص تشخیص افتراقی هستی."},
        {"role": "assistant", "content": "سلام، من دستیار پزشکی شما هستم. چه مشکلی دارید؟"}
    ]
    
    # سناریوی بیمار که اطلاعات کمی می‌دهد
    scenarios = [
        "گردنم درد می‌کند.",
        "نمی‌دانم، فقط درد دارم.",
        "شاید چند روزی می‌شود.",
        "نمی‌دانم، معمولی است."
    ]

    for i, user_input in enumerate(scenarios):
        chat_history.append({"role": "user", "content": user_input})
        print(f"\n[مرحله {i+1}] بیمار: {user_input}")
        
        # استفاده از تابع chat موجود در LLMService
        response = await llm_service.chat(chat_history)
        
        print(f"--> دستیار بالینی: {response}")
        chat_history.append({"role": "assistant", "content": response})
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_test())