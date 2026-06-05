
from openai import OpenAI
import os
from app.core.config import settings

print("OpenAI package version:", OpenAI.__version__ if hasattr(OpenAI, "__version__") else "unknown")
print("Environment variables that start with OPENAI_ or GAPGPT_:")
for key, value in os.environ.items():
    if key.startswith("OPENAI_") or key.startswith("GAPGPT_") or key.startswith("HTTP_PROXY") or key.startswith("HTTPS_PROXY"):
        print(f"  {key} = {value}")

print("\nSettings gapgpt_api_key:", settings.gapgpt_api_key)
print("Settings gapgpt_base_url:", settings.gapgpt_base_url)

try:
    client = OpenAI(
        base_url=settings.gapgpt_base_url,
        api_key=settings.gapgpt_api_key
    )
    print("OpenAI client created successfully!")
except Exception as e:
    print("Error creating client:", type(e), str(e))
    import traceback
    print("\nFull traceback:")
    print(traceback.format_exc())
