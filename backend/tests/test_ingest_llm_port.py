import pytest

from app.ingest.extract.llm_port import (
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
