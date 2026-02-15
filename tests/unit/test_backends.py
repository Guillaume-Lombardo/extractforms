from __future__ import annotations

import pytest

from extractforms.backends.multimodal_openai import MultimodalLLMBackend
from extractforms.backends.ocr_document_intelligence import OCRBackend
from extractforms.exceptions import BackendError
from extractforms.typing.models import RenderedPage
from extractforms.settings import Settings


def _settings(*, base_url: str | None, api_key: str | None, model: str = "gpt-4o-mini") -> Settings:
    settings = Settings()
    settings.openai_base_url = base_url
    settings.openai_api_key = api_key
    settings.openai_model = model
    return settings


class _FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            "choices": [{"message": {"content": '{"name":"demo","fields":[]}'}}],
        }


class _FakeClient:
    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001, ANN201
        return None

    def post(self, url: str, headers: dict, json: dict) -> _FakeResponse:  # noqa: A002
        assert url.endswith("/chat/completions")
        assert "Authorization" in headers
        assert "model" in json
        return _FakeResponse()


class _FakeHttpxModule:
    Client = _FakeClient

    class Limits:
        def __init__(self, max_connections: int) -> None:
            self.max_connections = max_connections


def test_post_chat_completions_requires_base_url_and_key() -> None:
    backend = MultimodalLLMBackend(_settings(base_url=None, api_key=None))
    with pytest.raises(BackendError, match="OPENAI_BASE_URL"):
        backend._post_chat_completions({})


def test_post_chat_completions_success(monkeypatch) -> None:
    backend = MultimodalLLMBackend(_settings(base_url="https://llm.local/v1", api_key="secret", model="x"))

    monkeypatch.setattr("extractforms.backends.multimodal_openai.httpx", _FakeHttpxModule)
    payload, pricing = backend._post_chat_completions({"model": "x"})

    assert payload["usage"]["prompt_tokens"] == 10
    assert pricing is not None
    assert pricing.model == "x"


def test_infer_schema_and_extract_values_with_mocked_post(mocker) -> None:
    backend = MultimodalLLMBackend(_settings(base_url="https://llm.local/v1", api_key="secret"))
    page = RenderedPage(page_number=1, mime_type="image/png", data_base64="AA==")

    mocker.patch.object(
        backend,
        "_post_chat_completions",
        side_effect=[
            (
                {"choices": [{"message": {"content": '{"name":"demo","fields":[]}'}}]},
                None,
            ),
            (
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"fields":[{"key":"a","value":"v","page":1,"confidence":"high"}]}'
                            }
                        }
                    ]
                },
                None,
            ),
        ],
    )

    schema, _ = backend.infer_schema([page])
    values, _ = backend.extract_values([page], ["a"])

    assert schema.name == "demo"
    assert values[0].key == "a"


def test_ocr_backend_is_stub() -> None:
    backend = OCRBackend()
    with pytest.raises(BackendError):
        backend.infer_schema([])


def test_post_chat_completions_requires_api_key() -> None:
    backend = MultimodalLLMBackend(_settings(base_url="https://llm.local/v1", api_key=""))
    with pytest.raises(BackendError, match="OPENAI_API_KEY"):
        backend._post_chat_completions({})


def test_image_content_builder() -> None:
    page = RenderedPage(page_number=1, mime_type="image/png", data_base64="AA==")
    content = MultimodalLLMBackend._image_content(page)
    assert content["image_url"]["url"].startswith("data:image/png;base64,")
