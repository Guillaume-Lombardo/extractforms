from __future__ import annotations

import pytest

from extractforms.backends import multimodal_openai
from extractforms.backends.multimodal_openai import MultimodalLLMBackend
from extractforms.backends.ocr_document_intelligence import OCRBackend
from extractforms.exceptions import BackendError
from extractforms.settings import Settings
from extractforms.typing.models import RenderedPage


def _settings(*, base_url: str | None, api_key: str | None, model: str = "gpt-4o-mini") -> Settings:
    settings = Settings()
    settings.openai_base_url = base_url
    settings.openai_api_key = api_key
    settings.openai_model = model
    return settings


class _FakeClient:
    pass


class _FakeCompletion:
    def model_dump(self, *, mode: str = "json") -> dict:
        assert mode == "json"
        return {
            "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            "choices": [{"message": {"content": '{"name":"demo","fields":[]}'}}],
        }


class _FakeCompletions:
    def create(self, **payload: object) -> _FakeCompletion:
        assert payload["model"] == "x"
        return _FakeCompletion()


class _FakeChat:
    completions = _FakeCompletions()


class _FakeOpenAIClient:
    chat = _FakeChat()


class _FakeOpenAI:
    def __new__(cls, *, api_key: str, base_url: str, http_client: _FakeClient) -> _FakeOpenAIClient:
        assert api_key == "test-api-key"  # pragma: allowlist secret
        assert base_url == "https://llm.local/v1"
        assert isinstance(http_client, _FakeClient)
        return _FakeOpenAIClient()


def test_post_chat_completions_requires_base_url_and_key() -> None:
    backend = MultimodalLLMBackend(_settings(base_url=None, api_key=None))
    with pytest.raises(BackendError, match="OPENAI_BASE_URL"):
        backend._post_chat_completions({})


def test_post_chat_completions_success(monkeypatch) -> None:
    backend = MultimodalLLMBackend(
        _settings(
            base_url="https://llm.local/v1",
            api_key="test-api-key",  # pragma: allowlist secret
            model="x",
        ),
    )
    monkeypatch.setattr(
        Settings,
        "select_sync_httpx_client",
        lambda _self, _target_url: _FakeClient(),
    )

    monkeypatch.setattr(multimodal_openai, "OpenAI", _FakeOpenAI)

    payload, pricing = backend._post_chat_completions({"model": "x"})

    assert payload["usage"]["prompt_tokens"] == 10
    assert pricing is not None
    assert pricing.model == "x"


def test_infer_schema_and_extract_values_with_mocked_post(mocker) -> None:
    backend = MultimodalLLMBackend(
        _settings(
            base_url="https://llm.local/v1",
            api_key="test-api-key",  # pragma: allowlist secret
        ),
    )
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
                                "content": '{"fields":[{"key":"a","value":"v","page":1,"confidence":"high"}]}',
                            },
                        },
                    ],
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
