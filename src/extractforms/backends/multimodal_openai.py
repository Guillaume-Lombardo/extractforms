"""OpenAI-compatible multimodal backend."""

from __future__ import annotations

import json
from typing import Any

try:
    import httpx
except Exception:  # pragma: no cover - optional dependency at runtime
    httpx: Any
    httpx = None

from pydantic import BaseModel, ConfigDict

from extractforms.exceptions import BackendError
from extractforms.logging import get_logger
from extractforms.models import FieldValue, PricingCall, RenderedPage, SchemaField, SchemaSpec
from extractforms.prompts import (
    build_schema_inference_prompt,
    build_values_extraction_prompt,
    schema_response_format,
)
from extractforms.settings import Settings, build_httpx_client_kwargs

logger = get_logger(__name__)


class _SchemaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    fields: list[SchemaField]


class _ValuesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[FieldValue]


class MultimodalLLMBackend:
    """Multimodal extraction backend against OpenAI-compatible endpoints."""

    def __init__(self, settings: Settings) -> None:
        """Initialize backend.

        Args:
            settings: Runtime settings.
        """
        self._settings = settings

    def _post_chat_completions(self, payload: dict[str, Any]) -> tuple[dict[str, Any], PricingCall | None]:
        """Send one completion request.

        Args:
            payload: Request payload.

        Raises:
            BackendError: If request fails or endpoint is misconfigured.

        Returns:
            tuple[dict[str, Any], PricingCall | None]: Parsed payload and optional pricing call.
        """
        if not self._settings.openai_base_url:
            raise BackendError(message="OPENAI_BASE_URL is required for multimodal backend")
        if not self._settings.openai_api_key:
            raise BackendError(message="OPENAI_API_KEY is required for multimodal backend")

        if httpx is None:
            raise BackendError(message="httpx is required for multimodal backend")

        kwargs = build_httpx_client_kwargs(self._settings)
        kwargs["limits"] = httpx.Limits(max_connections=self._settings.max_connections)

        url = f"{self._settings.openai_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(**kwargs) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            raise BackendError(message="Chat completion request failed") from exc

        usage = data.get("usage", {})
        pricing = PricingCall(
            provider="openai-compatible",
            model=self._settings.openai_model,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
            total_cost_usd=None,
        )

        return data, pricing

    @staticmethod
    def _image_content(page: RenderedPage) -> dict[str, Any]:
        """Build image content chunk.

        Args:
            page: Rendered page.

        Returns:
            dict[str, Any]: OpenAI content block.
        """
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{page.mime_type};base64,{page.data_base64}"},
        }

    def infer_schema(self, pages: list[RenderedPage]) -> tuple[SchemaSpec, PricingCall | None]:
        """Infer schema from rendered pages.

        Args:
            pages: Rendered pages.

        Returns:
            tuple[SchemaSpec, PricingCall | None]: Inferred schema and call pricing.
        """
        if not pages:
            raise BackendError(message="Cannot infer schema from empty page list")

        prompt = build_schema_inference_prompt()
        response_format = schema_response_format("schema_response", _SchemaResponse.model_json_schema())

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content.extend(self._image_content(page) for page in pages)

        payload = {
            "model": self._settings.openai_model,
            "messages": [{"role": "user", "content": content}],
            "response_format": {
                "type": "json_schema",
                "json_schema": response_format.model_dump(mode="json", by_alias=True),
            },
        }

        data, pricing = self._post_chat_completions(payload)
        content_text = data["choices"][0]["message"]["content"]
        parsed = _SchemaResponse.model_validate(json.loads(content_text))

        schema = SchemaSpec(
            id="",
            name=parsed.name,
            fingerprint="",
            fields=parsed.fields,
        )
        logger.info("Schema inferred", extra={"fields": len(schema.fields)})
        return schema, pricing

    def extract_values(
        self,
        pages: list[RenderedPage],
        keys: list[str],
        *,
        extra_instructions: str | None = None,
    ) -> tuple[list[FieldValue], PricingCall | None]:
        """Extract values for specific keys.

        Args:
            pages: Rendered pages.
            keys: Keys to extract.
            extra_instructions: Optional prompt augmentation.

        Returns:
            tuple[list[FieldValue], PricingCall | None]: Extracted values and pricing.
        """
        if not pages:
            raise BackendError(message="Cannot extract values from empty page list")

        schema = SchemaSpec(
            id="",
            name="runtime",
            fingerprint="",
            fields=[SchemaField(key=k, label=k) for k in keys],
        )
        prompt = build_values_extraction_prompt(schema, extra_instructions=extra_instructions)
        response_format = schema_response_format("values_response", _ValuesResponse.model_json_schema())

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content.extend(self._image_content(page) for page in pages)

        payload = {
            "model": self._settings.openai_model,
            "messages": [{"role": "user", "content": content}],
            "response_format": {
                "type": "json_schema",
                "json_schema": response_format.model_dump(mode="json", by_alias=True),
            },
        }

        data, pricing = self._post_chat_completions(payload)
        content_text = data["choices"][0]["message"]["content"]
        parsed = _ValuesResponse.model_validate(json.loads(content_text))
        logger.info("Values extracted", extra={"fields": len(parsed.fields)})
        return parsed.fields, pricing
