"""OpenAI-compatible multimodal backend."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

try:
    import httpx
except Exception:  # pragma: no cover - optional dependency at runtime
    httpx: Any
    httpx = None

try:
    import openai as openai_sdk
except Exception:  # pragma: no cover - optional dependency at runtime
    openai_sdk: Any
    openai_sdk = None

from pydantic import BaseModel, ConfigDict

from extractforms import logger
from extractforms.exceptions import BackendError
from extractforms.prompts import (
    build_schema_inference_prompt,
    build_values_extraction_prompt,
    schema_response_format,
)
from extractforms.typing.models import FieldValue, PricingCall, RenderedPage, SchemaField, SchemaSpec

if TYPE_CHECKING:
    from extractforms.settings import Settings


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
            settings (Settings): Runtime settings.
        """
        self._settings = settings

    def _post_chat_completions(self, payload: dict[str, Any]) -> tuple[dict[str, Any], PricingCall | None]:
        """Send one completion request.

        Args:
            payload (dict[str, Any]): Request payload.

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
        if openai_sdk is None:
            raise BackendError(message="openai is required for multimodal backend")

        client = self._settings.select_sync_httpx_client(self._settings.openai_base_url)
        if client is None:
            raise BackendError(message="httpx clients are not initialized in settings")
        http_client = cast("Any", client)
        openai_client = openai_sdk.OpenAI(
            api_key=self._settings.openai_api_key,
            base_url=self._settings.openai_base_url,
            http_client=http_client,
        )

        try:
            completion = openai_client.chat.completions.create(**payload)
            data = completion.model_dump(mode="json")
        except Exception as exc:
            status_error_type = getattr(openai_sdk, "APIStatusError", None)
            timeout_error_type = getattr(openai_sdk, "APITimeoutError", None)
            connection_error_type = getattr(openai_sdk, "APIConnectionError", None)

            if status_error_type and isinstance(exc, status_error_type):
                status_code = getattr(exc, "status_code", None)
                raise BackendError(
                    message=f"Chat completion request failed with status {status_code}",
                ) from exc
            if timeout_error_type and isinstance(exc, timeout_error_type):
                raise BackendError(message="Chat completion request timed out") from exc
            if connection_error_type and isinstance(exc, connection_error_type):
                raise BackendError(message=f"Chat completion request failed: {exc}") from exc
            raise BackendError(
                message=f"Chat completion request failed: {exc}",
            ) from exc

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
            page (RenderedPage): Rendered page.

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
            pages (list[RenderedPage]): Rendered pages.

        Raises:
            BackendError: If page list is empty.

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
            pages (list[RenderedPage]): Rendered pages.
            keys (list[str]): Keys to extract.
            extra_instructions (str | None): Optional prompt augmentation.

        Raises:
            BackendError: If page list is empty.

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
