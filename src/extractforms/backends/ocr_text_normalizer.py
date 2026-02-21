"""Optional text-only LLM normalization for OCR extracted values."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from extractforms.async_runner import run_async
from extractforms.exceptions import BackendError
from extractforms.typing.models import PricingCall

if TYPE_CHECKING:
    from extractforms.settings import Settings


class OCRTextLLMNormalizer:
    """Text-only normalizer for OCR values using OpenAI-compatible chat completions."""

    def __init__(self, settings: Settings) -> None:
        """Initialize normalizer.

        Args:
            settings (Settings): Runtime settings.
        """
        self._settings = settings

    def normalize_values(
        self,
        values: dict[str, str],
        *,
        extra_instructions: str | None = None,
    ) -> tuple[dict[str, str], PricingCall | None]:
        """Normalize extracted values.

        Args:
            values (dict[str, str]): Raw key/value mapping.
            extra_instructions (str | None): Optional runtime instructions.

        Returns:
            tuple[dict[str, str], PricingCall | None]: Normalized mapping and pricing.
        """
        if not values:
            return {}, None
        return run_async(self.anormalize_values(values, extra_instructions=extra_instructions))

    async def anormalize_values(
        self,
        values: dict[str, str],
        *,
        extra_instructions: str | None = None,
    ) -> tuple[dict[str, str], PricingCall | None]:
        """Normalize extracted values asynchronously.

        Args:
            values (dict[str, str]): Raw key/value mapping.
            extra_instructions (str | None): Optional runtime instructions.

        Returns:
            tuple[dict[str, str], PricingCall | None]: Normalized mapping and pricing.
        """
        self._validate_endpoint_settings()
        model = self._settings.ocr_text_normalization_model or self._settings.openai_model
        payload = self._build_payload(values=values, model=model, extra_instructions=extra_instructions)
        data = await self._call_completion(payload)
        return _parse_normalized_output(values=values, data=data, model=model)

    def _validate_endpoint_settings(self) -> None:
        """Validate endpoint settings required for text normalization.

        Raises:
            BackendError: If endpoint configuration is incomplete.
        """
        if not self._settings.openai_base_url:
            raise BackendError(message="OPENAI_BASE_URL is required for OCR text normalization")
        if not self._settings.openai_api_key:
            raise BackendError(message="OPENAI_API_KEY is required for OCR text normalization")

    @staticmethod
    def _build_payload(
        *,
        values: dict[str, str],
        model: str,
        extra_instructions: str | None,
    ) -> dict[str, object]:
        """Build chat.completions payload for OCR normalization.

        Args:
            values (dict[str, str]): Raw values.
            model (str): Target model.
            extra_instructions (str | None): Optional additional instructions.

        Returns:
            dict[str, object]: Payload object.
        """
        instructions = (
            "Normalize each provided value without inventing missing data. "
            "Return a compact JSON object with exactly one top-level key `values` "
            "mapping input keys to normalized string values."
        )
        if extra_instructions:
            instructions = f"{instructions}\nAdditional instructions:\n{extra_instructions}"
        return {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": f"{instructions}\nInput JSON:\n{json.dumps(values, ensure_ascii=False)}",
                },
            ],
            "response_format": {"type": "json_object"},
        }

    async def _call_completion(self, payload: dict[str, object]) -> dict[str, Any]:
        """Execute chat.completions request and return raw payload.

        Args:
            payload (dict[str, object]): Completion payload.

        Raises:
            BackendError: If request fails.

        Returns:
            dict[str, Any]: Completion payload.
        """
        client = self._settings.select_async_httpx_client(self._settings.openai_base_url)
        if client is None:
            raise BackendError(message="httpx clients are not initialized in settings")
        http_client = cast("Any", client)
        openai_client = AsyncOpenAI(
            api_key=self._settings.openai_api_key,
            base_url=self._settings.openai_base_url,
            http_client=http_client,
        )
        try:
            completion = await openai_client.chat.completions.create(**cast("Any", payload))
            return completion.model_dump(mode="json")
        except APIStatusError as exc:
            status_code = getattr(exc, "status_code", None)
            raise BackendError(
                message=f"OCR normalization request failed with status {status_code}",
            ) from exc
        except APITimeoutError as exc:
            raise BackendError(message="OCR normalization request timed out") from exc
        except APIConnectionError as exc:
            raise BackendError(message=f"OCR normalization request failed: {exc}") from exc
        except Exception as exc:
            raise BackendError(message=f"OCR normalization request failed: {exc}") from exc


def _parse_normalized_output(
    *,
    values: dict[str, str],
    data: dict[str, Any],
    model: str,
) -> tuple[dict[str, str], PricingCall | None]:
    """Parse normalizer output and map it to input keys.

    Args:
        values (dict[str, str]): Input values.
        data (dict[str, Any]): Completion payload.
        model (str): Model identifier used for pricing.

    Returns:
        tuple[dict[str, str], PricingCall | None]: Normalized mapping and pricing.
    """
    usage = data.get("usage", {})
    pricing = PricingCall(
        provider="openai-compatible",
        model=model,
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
        total_cost_usd=None,
    )
    normalized = _extract_normalized_values_map(data)
    if normalized is None:
        return values, pricing

    output: dict[str, str] = {}
    for key, raw in values.items():
        candidate = normalized.get(key, raw)
        output[key] = str(candidate)
    return output, pricing


def _extract_normalized_values_map(data: dict[str, Any]) -> dict[str, object] | None:
    """Extract normalized values map from completion payload.

    Args:
        data (dict[str, Any]): Completion payload.

    Returns:
        dict[str, object] | None: Parsed normalized values map, if present.
    """
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    content_text = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content_text, str):
        return None
    try:
        parsed = json.loads(content_text)
    except json.JSONDecodeError:
        return None
    normalized = parsed.get("values")
    return normalized if isinstance(normalized, dict) else None
