from __future__ import annotations

import asyncio

from extractforms.backends.ocr_text_normalizer import OCRTextLLMNormalizer
from extractforms.settings import Settings


def test_normalize_values_falls_back_on_missing_choices(monkeypatch) -> None:
    settings = Settings()
    settings.openai_base_url = "https://llm.local/v1"
    settings.openai_api_key = "test-api-key"  # pragma: allowlist secret
    normalizer = OCRTextLLMNormalizer(settings)

    async def _fake_call_completion(payload):
        _ = payload
        await asyncio.sleep(0)
        return {}

    monkeypatch.setattr(normalizer, "_call_completion", _fake_call_completion)
    output, pricing = normalizer.normalize_values({"a": "raw"})

    assert output == {"a": "raw"}
    assert pricing is not None


def test_normalize_values_falls_back_on_invalid_json(monkeypatch) -> None:
    settings = Settings()
    settings.openai_base_url = "https://llm.local/v1"
    settings.openai_api_key = "test-api-key"  # pragma: allowlist secret
    normalizer = OCRTextLLMNormalizer(settings)

    async def _fake_call_completion(payload):
        _ = payload
        await asyncio.sleep(0)
        return {"choices": [{"message": {"content": "{invalid-json"}}]}

    monkeypatch.setattr(normalizer, "_call_completion", _fake_call_completion)
    output, pricing = normalizer.normalize_values({"a": "raw"})

    assert output == {"a": "raw"}
    assert pricing is not None
