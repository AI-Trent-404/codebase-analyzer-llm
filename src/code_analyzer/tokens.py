"""
Token counting & budgeting.

Adhering to token limits is an explicit assignment requirement. We keep this in
one small module with a clean interface so the rest of the code can reason about
budgets without caring *how* tokens are counted.

Backend selection:
    * If ``tiktoken`` is installed we use ``cl100k_base`` as a close, fast proxy.
      (Anthropic's tokenizer is not public; cl100k over-estimates slightly, which
      is the safe direction for a budget.)
    * Otherwise we fall back to a well-known heuristic (~4 chars/token) that needs
      no dependencies and keeps unit tests deterministic and offline.
"""
from __future__ import annotations

from functools import lru_cache

_CHARS_PER_TOKEN = 4.0


@lru_cache(maxsize=1)
def _tiktoken_encoder():
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:  # pragma: no cover - optional dependency
        return None


def count_tokens(text: str) -> int:
    """Estimate the number of tokens in ``text``."""
    if not text:
        return 0
    enc = _tiktoken_encoder()
    if enc is not None:
        return len(enc.encode(text))
    return int(len(text) / _CHARS_PER_TOKEN) + 1


def fits_budget(text: str, budget: int) -> bool:
    return count_tokens(text) <= budget


def split_to_budget(text: str, budget: int) -> list[str]:
    """
    Split ``text`` into contiguous chunks that each fit within ``budget`` tokens,
    preferring to break on line boundaries so code stays readable to the model.
    """
    if fits_budget(text, budget):
        return [text]

    lines = text.splitlines(keepends=True)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for line in lines:
        line_tokens = count_tokens(line)
        # A single pathological line larger than the budget: hard-split it.
        if line_tokens > budget:
            if current:
                chunks.append("".join(current))
                current, current_tokens = [], 0
            chunks.extend(_hard_split(line, budget))
            continue

        if current_tokens + line_tokens > budget:
            chunks.append("".join(current))
            current, current_tokens = [line], line_tokens
        else:
            current.append(line)
            current_tokens += line_tokens

    if current:
        chunks.append("".join(current))
    return chunks


def _hard_split(text: str, budget: int) -> list[str]:
    approx_chars = max(1, int(budget * _CHARS_PER_TOKEN))
    return [text[i : i + approx_chars] for i in range(0, len(text), approx_chars)]
