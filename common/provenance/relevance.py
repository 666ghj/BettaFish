"""Conservative lexical relevance helpers shared by selection and claim gates."""

from __future__ import annotations

import re
from typing import Any, Mapping


_LATIN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,}")
_HAN_SEQUENCE_RE = re.compile(r"[\u4e00-\u9fff]+")
_STOPWORDS = {
    "about",
    "after",
    "also",
    "analysis",
    "and",
    "are",
    "data",
    "for",
    "from",
    "has",
    "have",
    "information",
    "into",
    "its",
    "report",
    "that",
    "the",
    "this",
    "was",
    "were",
    "with",
    "以及",
    "信息",
    "分析",
    "当前",
    "情况",
    "报告",
    "数据",
    "有关",
    "本章",
    "相关",
    "研究",
    "进行",
}


def flatten_text(value: Any) -> str:
    """Flatten structured evidence values without losing their field names."""
    if isinstance(value, Mapping):
        return " ".join(f"{key} {flatten_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return " ".join(flatten_text(item) for item in value)
    return str(value or "")


def meaningful_tokens(value: Any) -> set[str]:
    """Return words and Han bigrams, deliberately excluding single Han chars.

    Single-character overlap (for example ``中`` or ``的``) is too weak to
    establish either retrieval relevance or evidentiary support.
    """
    text = flatten_text(value).lower()
    tokens = set(_LATIN_TOKEN_RE.findall(text))
    for sequence in _HAN_SEQUENCE_RE.findall(text):
        if len(sequence) >= 2:
            tokens.add(sequence)
            tokens.update(
                sequence[index : index + 2]
                for index in range(len(sequence) - 1)
            )
    return {item for item in tokens if item not in _STOPWORDS}


def shared_meaningful_tokens(left: Any, right: Any) -> set[str]:
    """Return non-trivial lexical overlap between two values."""
    return meaningful_tokens(left) & meaningful_tokens(right)


def is_textually_related(left: Any, right: Any) -> bool:
    """Conservatively decide whether two texts discuss at least one same fact.

    This is intentionally an admission gate, not a semantic similarity model:
    uncertain paraphrases are omitted instead of attaching an unrelated source.
    """
    return bool(shared_meaningful_tokens(left, right))


def _compact_text(value: Any) -> str:
    """Keep only searchable letters and digits for phrase-coverage checks."""
    return "".join(
        character
        for character in flatten_text(value).lower()
        if character.isalnum() or "\u4e00" <= character <= "\u9fff"
    )


def _longest_common_substring_length(left: str, right: str) -> int:
    """Return the longest contiguous overlap without allocating a full matrix."""
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    longest = 0
    for left_character in left:
        current = [0] * (len(right) + 1)
        for index, right_character in enumerate(right, start=1):
            if left_character == right_character:
                current[index] = previous[index - 1] + 1
                longest = max(longest, current[index])
        previous = current
    return longest


def is_claim_text_supported(claim: Any, evidence: Any) -> bool:
    """Require evidence to cover the claim, not merely mention its subject.

    Evidence selection intentionally uses a broad lexical match for recall.  A
    factual claim needs a stricter boundary: most of its meaningful tokens, or
    most of one sufficiently informative contiguous phrase, must occur in the
    source-derived evidence text.  This rejects a claim such as ``鹅腿阿姨来自
    江西`` when the source only says ``鹅腿阿姨在清华摆摊``.
    """
    claim_tokens = meaningful_tokens(claim)
    evidence_tokens = meaningful_tokens(evidence)
    if not claim_tokens or not evidence_tokens:
        return False

    shared = claim_tokens & evidence_tokens
    token_coverage = len(shared) / len(claim_tokens)
    if len(shared) >= 2 and token_coverage >= 0.7:
        return True

    compact_claim = _compact_text(claim)
    compact_evidence = _compact_text(evidence)
    if len(compact_claim) < 6:
        return compact_claim == compact_evidence or compact_claim in compact_evidence

    phrase_coverage = (
        _longest_common_substring_length(compact_claim, compact_evidence)
        / len(compact_claim)
    )
    return phrase_coverage >= 0.8


__all__ = [
    "flatten_text",
    "is_claim_text_supported",
    "is_textually_related",
    "meaningful_tokens",
    "shared_meaningful_tokens",
]
