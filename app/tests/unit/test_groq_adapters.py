from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from groq import APIConnectionError, BadRequestError, RateLimitError
from pydantic import BaseModel

from app.integrations.asr.whisper_adapter import WhisperAdapter
from app.integrations.llm.llama_adapter import LLaMAAdapter


class _Schema(BaseModel):
    title: str
    items: list[str]


def _http_response(status_code: int) -> httpx.Response:
    request = httpx.Request("POST", "https://api.groq.com/test")
    return httpx.Response(status_code, request=request)


def _llm_with_client(client: MagicMock) -> LLaMAAdapter:
    adapter = LLaMAAdapter(api_key="test-key", model_name="test-model")
    adapter._client = client
    return adapter


def _completion(content: str | None) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_llm_generate_returns_text_and_builds_messages():
    client = MagicMock()
    client.chat.completions.create.return_value = _completion("Pong")
    adapter = _llm_with_client(client)

    assert adapter.generate("Ping", system_prompt="sistema") == "Pong"

    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "test-model"
    assert kwargs["messages"] == [
        {"role": "system", "content": "sistema"},
        {"role": "user", "content": "Ping"},
    ]


def test_llm_generate_returns_empty_string_when_content_is_none():
    client = MagicMock()
    client.chat.completions.create.return_value = _completion(None)

    assert _llm_with_client(client).generate("Ping") == ""


def test_llm_missing_api_key_raises_runtime_error_only_on_use():
    adapter = LLaMAAdapter(api_key="")
    adapter.api_key = ""

    with pytest.raises(RuntimeError):
        adapter.generate("Ping")


@pytest.mark.parametrize(
    "error",
    [
        RateLimitError("limite", response=_http_response(429), body=None),
        BadRequestError("invalido", response=_http_response(400), body=None),
        APIConnectionError(request=httpx.Request("POST", "https://api.groq.com/test")),
    ],
)
def test_llm_groq_errors_become_sanitized_runtime_error(error: Exception):
    client = MagicMock()
    client.chat.completions.create.side_effect = error

    with pytest.raises(RuntimeError) as exc_info:
        _llm_with_client(client).generate("Ping")

    assert "groq" not in str(exc_info.value).lower()
    assert "api.groq.com" not in str(exc_info.value)


def test_llm_generate_structured_validates_schema():
    client = MagicMock()
    client.chat.completions.create.return_value = _completion('{"title": "T", "items": ["a", "b"]}')

    result = _llm_with_client(client).generate_structured("prompt", _Schema)

    assert result == _Schema(title="T", items=["a", "b"])
    assert client.chat.completions.create.call_args.kwargs["response_format"]["type"] == "json_schema"


def test_llm_generate_structured_rejects_invalid_json():
    client = MagicMock()
    client.chat.completions.create.return_value = _completion("no es json")

    with pytest.raises(RuntimeError):
        _llm_with_client(client).generate_structured("prompt", _Schema)


def _asr_with_client(client: MagicMock) -> WhisperAdapter:
    adapter = WhisperAdapter(api_key="test-key", model_name="whisper-test")
    adapter._client = client
    return adapter


def test_asr_transcribe_returns_payload_with_confidence(tmp_path: Path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....")
    client = MagicMock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(
        text="  hola mundo  ",
        segments=[{"avg_logprob": -0.1}, {"avg_logprob": -0.3}],
    )

    result = _asr_with_client(client).transcribe(audio, language="es")

    assert result["text"] == "hola mundo"
    assert result["raw_text"] == "hola mundo"
    assert result["language"] == "es"
    assert result["model_name"] == "whisper-test"
    assert 0.0 < result["confidence"] <= 100.0


def test_asr_transcribe_confidence_is_none_without_segments(tmp_path: Path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....")
    client = MagicMock()
    client.audio.transcriptions.create.return_value = SimpleNamespace(text="hola", segments=None)

    assert _asr_with_client(client).transcribe(audio)["confidence"] is None


def test_asr_transcribe_missing_file_raises_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        _asr_with_client(MagicMock()).transcribe(tmp_path / "no_existe.wav")


def test_asr_groq_error_becomes_sanitized_runtime_error(tmp_path: Path):
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"RIFF....")
    client = MagicMock()
    client.audio.transcriptions.create.side_effect = RateLimitError(
        "limite", response=_http_response(429), body=None
    )

    with pytest.raises(RuntimeError) as exc_info:
        _asr_with_client(client).transcribe(audio)

    assert "groq" not in str(exc_info.value).lower()
