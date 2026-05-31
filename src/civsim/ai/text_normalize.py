"""Light typo fixes for player invention text before LLM interpretation."""

from __future__ import annotations

# Whole-word / phrase typos (lowercase key)
INVENTION_TYPOS: dict[str, str] = {
    "cjarcoa": "charcoal",
    "cjarcoal": "charcoal",
    "charcaol": "charcoal",
    "charocol": "charcoal",
    "charcol": "charcoal",
    "firre": "fire",
    "watter": "water",
    "bonetools": "bone tools",
    "smokehole": "smoke hole",
}


def normalize_invention_text(text: str) -> tuple[str, str | None]:
    """
    Return (text_for_llm, correction_note).
    correction_note is a short hint when a typo was fixed, else None.
    """
    stripped = text.strip()
    if not stripped:
        return text, None

    lower = stripped.lower()
    correct_words = set(INVENTION_TYPOS.values())
    if lower in correct_words:
        return stripped, None

    if lower in INVENTION_TYPOS:
        fixed = INVENTION_TYPOS[lower]
        return (
            f"{stripped} (player likely meant: {fixed})",
            f"Interpreted typo as «{fixed}»",
        )

    # Single-token close edits (one char swap / missing letter)
    for typo, fixed in INVENTION_TYPOS.items():
        if _close_match(lower, typo):
            return (
                f"{stripped} (player likely meant: {fixed})",
                f"Interpreted «{stripped}» as «{fixed}»",
            )

    return stripped, None


def _close_match(a: str, b: str, max_edits: int = 2) -> bool:
    if abs(len(a) - len(b)) > max_edits:
        return False
    if len(a) < 4:
        return False
    # Simple: same length, at most 2 differing positions
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= max_edits
    return False
