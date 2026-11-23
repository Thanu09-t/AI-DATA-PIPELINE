"""
Fuzzy matcher utilities: standalone fuzzy matching helpers.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from rapidfuzz import fuzz, process


def best_match(
    query: str,
    candidates: List[str],
    threshold: float = 0.85,
    scorer=fuzz.token_sort_ratio,
) -> Optional[Tuple[str, float]]:
    """
    Find the best fuzzy match for query in candidates.
    Returns (best_match_string, score_0_to_1) or None.
    threshold is in 0.0–1.0 range.
    """
    if not candidates or not query:
        return None
    result = process.extractOne(query, candidates, scorer=scorer, score_cutoff=threshold * 100)
    if result:
        return result[0], result[1] / 100.0
    return None


def deduplicate_names(
    names: List[str],
    threshold: float = 0.95,
) -> List[str]:
    """Return unique names, merging near-duplicates above threshold."""
    unique: List[str] = []
    for name in names:
        match = best_match(name, unique, threshold=threshold)
        if not match:
            unique.append(name)
    return unique
