import pytest

from app.config import CRM_XLSX_PATH, MEETINGS_DIR
from app.data.repository import load_repository


class StubLLM:
    """Deterministic fake LLMClient. Set `.payload` to the dict to return."""

    def __init__(self, payload=None):
        self.payload = payload or {}
        self.calls = []

    def generate_json(self, system: str, user: str) -> dict:
        self.calls.append((system, user))
        return self.payload


@pytest.fixture
def repo():
    return load_repository(CRM_XLSX_PATH, MEETINGS_DIR)


@pytest.fixture
def stub_llm():
    return StubLLM()
