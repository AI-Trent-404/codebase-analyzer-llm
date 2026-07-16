"""
Content-addressed cache.

Analyzing a codebase is the kind of thing you run repeatedly while iterating on
prompts or re-running after a few files change. Re-sending unchanged files to the
LLM wastes money and time. We key each cached result on a hash of
``(file content + model + prompt version)`` so:

* Editing a file invalidates only that file.
* Changing the model or the prompt invalidates everything (results would differ).
* Everything else is served instantly from disk.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .models import LLMFileInsight

# Bump when the extraction prompt changes in a way that alters outputs.
PROMPT_VERSION = "v1"


def _key(content: str, model: str) -> str:
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())
    h.update(b"\x00")
    h.update(model.encode())
    h.update(b"\x00")
    h.update(content.encode("utf-8", errors="replace"))
    return h.hexdigest()


class InsightCache:
    def __init__(self, cache_dir: Path, enabled: bool = True) -> None:
        self.enabled = enabled
        self.dir = Path(cache_dir)
        if self.enabled:
            self.dir.mkdir(parents=True, exist_ok=True)

    def get(self, content: str, model: str) -> LLMFileInsight | None:
        if not self.enabled:
            return None
        path = self.dir / f"{_key(content, model)}.json"
        if not path.exists():
            return None
        try:
            return LLMFileInsight.model_validate_json(path.read_text())
        except Exception:
            return None  # corrupt/stale entry -> treat as miss

    def put(self, content: str, model: str, insight: LLMFileInsight) -> None:
        if not self.enabled:
            return
        path = self.dir / f"{_key(content, model)}.json"
        path.write_text(insight.model_dump_json())
