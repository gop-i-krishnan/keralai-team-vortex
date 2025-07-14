"""
backend/api/llm/watsonx.py
WatsonxAdapter — calls IBM watsonx.ai Granite model.
Only used when JALSETU_MOCK_LLM=0.
Constitution P9: text is scrubbed of PII before being sent.
"""
from __future__ import annotations
import json
import os
from backend.api.llm.adapter import LLMAdapter
from backend.engine.parser import scrub_pii
from backend.engine.config import val

_PROMPT_TEMPLATE = """You are a logistics data extractor.
Extract shipment details from the text below.
Return ONLY a JSON object with these keys:
  weight_t (number or null), origin_raw (string or null),
  destination_raw (string or null), deadline_raw (string or null), confidence (0.0-1.0).
Do NOT include cost, price, recommendation, or any scoring.

Text: {text}

JSON:"""


class WatsonxAdapter(LLMAdapter):
    def __init__(self):
        try:
            from ibm_watsonx_ai import Credentials
            from ibm_watsonx_ai.foundation_models import ModelInference
            creds = Credentials(
                url=os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
                api_key=os.environ.get("WATSONX_API_KEY", ""),
            )
            self._model = ModelInference(
                model_id=val("llm", "model_id"),
                credentials=creds,
                project_id=os.environ.get("WATSONX_PROJECT_ID", ""),
            )
        except Exception as e:
            raise RuntimeError(f"WatsonxAdapter init failed: {e}. Set JALSETU_MOCK_LLM=1 for offline mode.")

    def parse_shipment_text(self, text: str) -> dict:
        clean = scrub_pii(text)  # Constitution P9: never send PII
        prompt = _PROMPT_TEMPLATE.format(text=clean)
        response = self._model.generate_text(prompt=prompt)
        try:
            # Extract JSON from response
            start = response.find("{")
            end = response.rfind("}") + 1
            return json.loads(response[start:end])
        except Exception:
            return {"weight_t": None, "origin_raw": None, "destination_raw": None,
                    "deadline_raw": None, "confidence": 0.0}
