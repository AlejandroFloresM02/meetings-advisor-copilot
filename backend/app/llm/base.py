"""Shared LLM interface used by generation + the agent's tools."""
from __future__ import annotations

import json
import re
from typing import Protocol


class LLMClient(Protocol):
    def generate_json(self, system: str, user: str) -> dict:
        """Return a parsed JSON object from the model (or {} on failure)."""
        ...


def parse_json_object(text: str) -> dict:
    """Best-effort: parse the first {...} block out of a model response."""
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}
    return {}
