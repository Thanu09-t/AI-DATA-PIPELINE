"""
Entity resolver: deterministic pipeline for canonicalizing entity names.

Pipeline:
1. Normalize whitespace
2. Remove irrelevant punctuation
3. Normalize case
4. Handle legal suffixes (Inc., LLC, Ltd., Co., Corp.)
5. Apply alias mapping
6. Compare against seed registry
7. RapidFuzz similarity scoring
8. Semantic similarity for ambiguous cases (via ChromaDB)
9. Log every mapping decision
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz, process

from src.monitoring.logger import get_logger

logger = get_logger("resolution.entity_resolver")
UTC = timezone.utc

# ─────────────────────────────────────────────────────────────────────────────
# Legal suffix patterns to strip
# ─────────────────────────────────────────────────────────────────────────────
_LEGAL_SUFFIXES = re.compile(
    r"\b(inc\.?|llc\.?|ltd\.?|co\.?|corp\.?|corporation|incorporated|"
    r"limited|plc\.?|gmbh|s\.a\.?|b\.v\.?|s\.r\.l\.?|ag\.?|oy|ab\.?|"
    r"holding|holdings|group|ventures|labs?|technologies|tech|ai|systems|"
    r"solutions|services|platform|platforms)\b\.?",
    re.I,
)

# ─────────────────────────────────────────────────────────────────────────────
# Seed registry: 50+ canonical AI organization names
# ─────────────────────────────────────────────────────────────────────────────
SEED_REGISTRY: Dict[str, str] = {
    # Canonical name → canonical name (identity mapping for lookup)
    "openai": "OpenAI",
    "google deepmind": "Google DeepMind",
    "deepmind": "Google DeepMind",
    "google brain": "Google Brain",
    "anthropic": "Anthropic",
    "meta ai": "Meta AI",
    "meta": "Meta AI",
    "microsoft research": "Microsoft Research",
    "microsoft": "Microsoft",
    "hugging face": "Hugging Face",
    "huggingface": "Hugging Face",
    "stability ai": "Stability AI",
    "stabilityai": "Stability AI",
    "cohere": "Cohere",
    "ai21 labs": "AI21 Labs",
    "ai21labs": "AI21 Labs",
    "mistral ai": "Mistral AI",
    "mistral": "Mistral AI",
    "databricks": "Databricks",
    "scale ai": "Scale AI",
    "inflection ai": "Inflection AI",
    "inflection": "Inflection AI",
    "adept": "Adept AI",
    "adept ai": "Adept AI",
    "character ai": "Character.AI",
    "character.ai": "Character.AI",
    "runway": "Runway",
    "runway ml": "Runway",
    "midjourney": "Midjourney",
    "elevenlabs": "ElevenLabs",
    "eleven labs": "ElevenLabs",
    "perplexity ai": "Perplexity AI",
    "perplexity": "Perplexity AI",
    "together ai": "Together AI",
    "together": "Together AI",
    "replicate": "Replicate",
    "modal labs": "Modal Labs",
    "modal": "Modal Labs",
    "lambda labs": "Lambda Labs",
    "coreweave": "CoreWeave",
    "core weave": "CoreWeave",
    "weights & biases": "Weights & Biases",
    "wandb": "Weights & Biases",
    "weights and biases": "Weights & Biases",
    "jasper ai": "Jasper AI",
    "jasper": "Jasper AI",
    "copy.ai": "Copy.ai",
    "copy ai": "Copy.ai",
    "notion": "Notion",
    "retool": "Retool",
    "lightricks": "Lightricks",
    "aleph alpha": "Aleph Alpha",
    "deepl": "DeepL",
    "synthesia": "Synthesia",
    "d-id": "D-ID",
    "did": "D-ID",
    "typeface": "Typeface",
    "aisera": "AISera",
    "imbue": "Imbue",
    "descript": "Descript",
    "linear": "Linear",
    "vercel": "Vercel",
    "clerk": "Clerk",
    "mem": "Mem",
    "nvidia": "NVIDIA",
    "amd": "AMD",
    "intel": "Intel",
    "aws": "Amazon Web Services",
    "amazon web services": "Amazon Web Services",
    "gcp": "Google Cloud",
    "google cloud": "Google Cloud",
    "azure": "Microsoft Azure",
    "microsoft azure": "Microsoft Azure",
    "ibm": "IBM",
    "baidu": "Baidu",
    "alibaba": "Alibaba",
    "tencent": "Tencent",
}

# Manual alias overrides (raw → canonical)
ALIAS_MAP: Dict[str, str] = {
    "open ai": "OpenAI",
    "openai inc": "OpenAI",
    "openai inc.": "OpenAI",
    "openai, inc.": "OpenAI",
    "openai corporation": "OpenAI",
    "google": "Google",
    "alphabet": "Alphabet / Google",
    "meta platforms": "Meta AI",
    "facebook": "Meta AI",
    "facebook ai": "Meta AI",
    "fair": "Meta AI",
    "apple": "Apple",
    "samsung": "Samsung",
}

FUZZY_HIGH_THRESHOLD = 90  # >= 90: high-confidence match
FUZZY_LOW_THRESHOLD = 75   # 75-89: requires review


def normalize_name(name: str) -> str:
    """
    Normalize entity name for comparison:
    1. Unicode normalize (NFKD)
    2. Lowercase
    3. Remove legal suffixes
    4. Remove punctuation (except & and -)
    5. Collapse whitespace
    """
    if not name:
        return ""
    # NFKD unicode normalization
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.lower().strip()
    # Remove legal suffixes
    name = _LEGAL_SUFFIXES.sub(" ", name)
    # Remove punctuation except & and -
    name = re.sub(r"[^\w\s&\-]", " ", name)
    # Collapse whitespace
    name = " ".join(name.split())
    return name


class EntityResolver:
    """
    Deterministic entity resolution pipeline.
    Maintains an in-memory mapping cache for the current pipeline run.
    """

    def __init__(self):
        self._cache: Dict[str, Tuple[str, str, float]] = {}  # raw → (canonical, method, score)
        self._mapping_log: List[Dict[str, Any]] = []
        self._canonical_names = list(SEED_REGISTRY.values())
        self._normalized_registry = {
            normalize_name(k): v for k, v in SEED_REGISTRY.items()
        }

    def resolve(
        self,
        raw_name: str,
        source_url: Optional[str] = None,
        record_type: Optional[str] = None,
    ) -> Tuple[str, str, float, bool]:
        """
        Resolve a raw entity name to its canonical form.

        Returns:
            (canonical_name, matching_method, confidence_score, requires_review)
        """
        if not raw_name or not raw_name.strip():
            return raw_name, "empty", 0.0, True

        raw_stripped = raw_name.strip()

        # Cache hit
        if raw_stripped in self._cache:
            cached = self._cache[raw_stripped]
            return cached[0], cached[1], cached[2], False

        # Step 1: Alias map check
        if raw_stripped.lower() in ALIAS_MAP:
            canonical = ALIAS_MAP[raw_stripped.lower()]
            self._record(raw_stripped, canonical, "alias_map", 1.0, source_url, record_type, False)
            return canonical, "alias_map", 1.0, False

        # Step 2: Normalize
        normalized = normalize_name(raw_stripped)

        # Step 3: Exact match against seed registry (normalized)
        if normalized in self._normalized_registry:
            canonical = self._normalized_registry[normalized]
            self._record(raw_stripped, canonical, "exact", 1.0, source_url, record_type, False)
            return canonical, "exact", 1.0, False

        # Step 4: RapidFuzz against canonical names
        norm_candidates = list(self._normalized_registry.keys())
        if norm_candidates:
            match_result = process.extractOne(
                normalized,
                norm_candidates,
                scorer=fuzz.token_sort_ratio,
            )
            if match_result:
                matched_norm, score, _ = match_result
                if score >= FUZZY_HIGH_THRESHOLD:
                    canonical = self._normalized_registry[matched_norm]
                    self._record(raw_stripped, canonical, "fuzzy_high", score / 100.0, source_url, record_type, False)
                    return canonical, "fuzzy_high", score / 100.0, False
                elif score >= FUZZY_LOW_THRESHOLD:
                    canonical = self._normalized_registry[matched_norm]
                    self._record(raw_stripped, canonical, "fuzzy_low", score / 100.0, source_url, record_type, True)
                    return canonical, "fuzzy_low", score / 100.0, True

        # Step 5: No match: return normalized name as canonical with review flag
        canonical_fallback = raw_stripped  # Keep original if no match
        self._record(raw_stripped, canonical_fallback, "manual_review", 0.0, source_url, record_type, True)
        return canonical_fallback, "manual_review", 0.0, True

    def _record(
        self,
        raw: str,
        canonical: str,
        method: str,
        score: float,
        source_url: Optional[str],
        record_type: Optional[str],
        requires_review: bool,
    ) -> None:
        normalized = normalize_name(raw)
        self._cache[raw] = (canonical, method, score)
        entry = {
            "raw_name": raw,
            "canonical_name": canonical,
            "normalized_name": normalized,
            "matching_method": method,
            "confidence_score": score,
            "source_url": source_url,
            "record_type": record_type,
            "resolved_at": datetime.now(UTC).isoformat(),
            "requires_review": requires_review,
            "notes": None,
        }
        self._mapping_log.append(entry)
        logger.debug(
            "Entity resolved",
            extra={
                "raw": raw,
                "canonical": canonical,
                "method": method,
                "score": score,
                "review": requires_review,
            },
        )

    def get_mapping_log(self) -> List[Dict[str, Any]]:
        return list(self._mapping_log)

    def stats(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for entry in self._mapping_log:
            m = entry["matching_method"]
            counts[m] = counts.get(m, 0) + 1
        return counts


# Singleton
_resolver: Optional[EntityResolver] = None


def get_resolver() -> EntityResolver:
    global _resolver
    if _resolver is None:
        _resolver = EntityResolver()
    return _resolver
