"""Mechanical, content-free text humanization for narrative assembly.

Turns closed-vocabulary snake_case values (theme tags, SemanticRole,
EvidenceStrength, Orientation) into human-readable phrases via a fixed
Title Case transform -- never a lookup against authored content, never
adding descriptive language. See
Documentation/NARRATIVE_LAYER_DESIGN.md Section 7 for why this is a
formatting utility, not new reference data or new interpretive content:
it is verified safe (idempotent, non-corrupting) against every one of
the 107 tags in theme_vocabulary.yaml.

Card.name, SpreadPosition.name, and Tension.label are already
human-readable and do not need this transform (design doc Section 7) --
passing one through is harmless (see this module's tests) but is not
this function's documented purpose.
"""

from __future__ import annotations

_MINOR_WORDS = frozenset({"and", "of", "the"})


def humanize_tag(value: str) -> str:
    """snake_case -> Title Case, with a small fixed minor-word exception
    list (kept lowercase unless it is the first word). Idempotent-safe on
    already space-separated, already-capitalized input.
    """
    words = value.replace("_", " ").split(" ")
    humanized = [
        word.lower() if index > 0 and word.lower() in _MINOR_WORDS else word.capitalize()
        for index, word in enumerate(words)
    ]
    return " ".join(humanized)
