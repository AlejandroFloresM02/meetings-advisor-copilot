import json

import pytest

from app.ingest.extract.llm_port import (
    OllamaLlmExtractor,
    RecordingLlmExtractor,
    ReplayLlmExtractor,
    llm_key,
)


class _StubLlm:
    def __init__(self, payload: dict):
        self.payload = payload

    def extract(self, system: str, user: str) -> dict:
        return self.payload


def test_llm_key_is_stable():
    assert llm_key("s", "u") == llm_key("s", "u")
    assert llm_key("s", "u") != llm_key("s", "v")


def test_llm_record_then_replay(tmp_path):
    rec = RecordingLlmExtractor(_StubLlm({"funded_ratio": 0.75}), tmp_path)
    assert rec.extract("sys", "usr") == {"funded_ratio": 0.75}

    replay = ReplayLlmExtractor(tmp_path)
    assert replay.extract("sys", "usr") == {"funded_ratio": 0.75}


def test_replay_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        ReplayLlmExtractor(tmp_path).extract("sys", "missing")


def test_ollama_extractor_posts_chat_and_parses_json():
    import httpx

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": '{"funded_ratio": 0.75}'}
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ex = OllamaLlmExtractor(model="qwen2.5:14b", client=client)
    out = ex.extract("Extract funded status.", "ACFR text here")

    assert out == {"funded_ratio": 0.75}
    assert seen["path"] == "/api/chat"
    assert seen["body"]["model"] == "qwen2.5:14b"
    assert seen["body"]["format"] == "json"
    assert seen["body"]["stream"] is False
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]
