import json
import httpx
from openai import OpenAI
from app.core.config import settings


class MedicalExtractor:

    def __init__(self):
        self.provider = settings.llm_provider
        self.client = None
        self.model = None
        
        # Use a custom httpx client to avoid the "proxies" argument error in some environments
        http_client = httpx.Client()
        
        if self.provider == "openai" and settings.openai_api_key:
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                http_client=http_client
            )
            self.model = settings.openai_model
        elif self.provider == "gapgpt" and settings.gapgpt_api_key:
            self.client = OpenAI(
                base_url=settings.gapgpt_base_url,
                api_key=settings.gapgpt_api_key,
                http_client=http_client
            )
            self.model = settings.gapgpt_model

    def _fallback_extract(self, text: str) -> dict:
        cleaned_text = text.strip()
        return {
            "chief_complaint": cleaned_text or None,
            "symptoms": [cleaned_text] if cleaned_text else [],
            "duration": "",
            "severity": "",
            "medications": [],
            "allergies": [],
            "past_diseases": [],
            "family_history": [],
            "social_history": {
                "smoking": "",
                "alcohol": "",
                "occupation": "",
            },
        }

    async def extract(self, text: str):
        if not self.client:
            return self._fallback_extract(text)

        prompt = f"""
Extract structured medical information from this patient message.

Return ONLY JSON.

Patient message:
{text}

JSON format:

{{
"chief_complaint": "",
"symptoms": [],
"duration": "",
"severity": "",
"medications": [],
"allergies": [],
"past_diseases": [],
"family_history": [],
"social_history": {{
"smoking": "",
"alcohol": "",
"occupation": ""
}}
}}
"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a medical data extraction system."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        content = response.choices[0].message.content

        try:
            return json.loads(content)
        except Exception:
            return self._fallback_extract(text)


medical_extractor = MedicalExtractor()
