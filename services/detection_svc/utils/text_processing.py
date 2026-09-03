"""Text processing utilities for fuzzy matching and similarity detection."""

import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set

# Levenshtein is an optional dependency — fall back to difflib if unavailable
try:
    import Levenshtein as _levenshtein

    def _lev_distance(a: str, b: str) -> int:
        return _levenshtein.distance(a, b)

except ImportError:
    def _lev_distance(a: str, b: str) -> int:
        """Pure-Python fallback for Levenshtein edit distance."""
        if not a:
            return len(b)
        if not b:
            return len(a)
        rows = len(a) + 1
        cols = len(b) + 1
        prev = list(range(cols))
        for i in range(1, rows):
            curr = [i] + [0] * (cols - 1)
            for j in range(1, cols):
                cost = 0 if a[i - 1] == b[j - 1] else 1
                curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
            prev = curr
        return prev[cols - 1]

# Stop words shared across key-phrase extraction and similarity weighting
_STOP_WORDS: Set[str] = {
    "the", "a", "an", "of", "to", "for", "with", "on", "at", "from",
    "by", "in", "as", "is", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "may", "might", "shall", "should", "must", "can", "etc", "and",
    "or", "but", "nor", "yet", "so", "then", "than", "that", "this",
    "these", "those", "it", "its",
}


class TextProcessor:
    """Advanced text processing for fuzzy matching.

    Provides normalisation, tokenisation, trigram / Levenshtein /
    sequence-match similarity, key-phrase extraction and invoice feature
    extraction — all stateless and safe to use from async code.
    """

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalise text for comparison.

        Steps:
        1. Lowercase
        2. Unicode NFKD → ASCII
        3. Keep only alphanumerics and spaces
        4. Collapse whitespace
        """
        if not text:
            return ""
        text = text.lower()
        text = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize normalised text into single words (len > 1)."""
        text = TextProcessor.normalize_text(text)
        return [w for w in text.split() if len(w) > 1]

    # ------------------------------------------------------------------
    # Key-phrase extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_key_phrases(text: str, max_phrases: int = 10) -> List[str]:
        """Extract key phrases (bigrams / trigrams) using simple NLP heuristics.

        Phrases are scored by normalised word-frequency overlap and
        returned most-relevant first.
        """
        if not text:
            return []

        words = TextProcessor.tokenize(text)
        if not words:
            return []

        filtered = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
        word_freq: Counter = Counter(filtered)

        # Build bigrams and trigrams from content words
        phrases: List[str] = []
        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i + 1]
            if w1 not in _STOP_WORDS and w2 not in _STOP_WORDS and len(w1) > 2 and len(w2) > 2:
                phrases.append(f"{w1} {w2}")

            if i < len(words) - 2:
                w3 = words[i + 2]
                if (
                    w1 not in _STOP_WORDS
                    and w2 not in _STOP_WORDS
                    and w3 not in _STOP_WORDS
                    and all(len(w) > 2 for w in (w1, w2, w3))
                ):
                    phrases.append(f"{w1} {w2} {w3}")

        phrase_scores: Dict[str, float] = {}
        for phrase in phrases:
            tokens = phrase.split()
            phrase_scores[phrase] = sum(word_freq.get(t, 0) for t in tokens) / len(tokens)

        sorted_phrases = sorted(phrase_scores.items(), key=lambda x: x[1], reverse=True)
        return [p[0] for p in sorted_phrases[:max_phrases]]

    # ------------------------------------------------------------------
    # Similarity algorithms
    # ------------------------------------------------------------------

    @staticmethod
    def compute_trigram_similarity(text1: str, text2: str) -> float:
        """Jaccard similarity over character trigrams (3-grams)."""
        t1 = TextProcessor.normalize_text(text1)
        t2 = TextProcessor.normalize_text(text2)
        if not t1 or not t2:
            return 0.0

        tri1: Set[str] = {t1[i : i + 3] for i in range(len(t1) - 2)}
        tri2: Set[str] = {t2[i : i + 3] for i in range(len(t2) - 2)}
        if not tri1 or not tri2:
            return 0.0

        return len(tri1 & tri2) / len(tri1 | tri2)

    @staticmethod
    def compute_levenshtein_similarity(text1: str, text2: str, normalize: bool = True) -> float:
        """Normalised Levenshtein similarity (1 - dist/max_len)."""
        if not text1 or not text2:
            return 0.0
        if normalize:
            text1 = TextProcessor.normalize_text(text1)
            text2 = TextProcessor.normalize_text(text2)

        distance = _lev_distance(text1, text2)
        max_len = max(len(text1), len(text2))
        if max_len == 0:
            return 1.0
        return 1.0 - (distance / max_len)

    @staticmethod
    def compute_sequence_similarity(text1: str, text2: str) -> float:
        """Ratcliff-Obershelp (SequenceMatcher) similarity."""
        if not text1 or not text2:
            return 0.0
        t1 = TextProcessor.normalize_text(text1)
        t2 = TextProcessor.normalize_text(text2)
        return SequenceMatcher(None, t1, t2).ratio()

    @staticmethod
    def compute_weighted_similarity(
        text1: str,
        text2: str,
        trigram_weight: float = 0.4,
        levenshtein_weight: float = 0.3,
        sequence_weight: float = 0.3,
    ) -> float:
        """Combine trigram, Levenshtein and SequenceMatcher similarities."""
        if not text1 or not text2:
            return 0.0

        tri = TextProcessor.compute_trigram_similarity(text1, text2)
        lev = TextProcessor.compute_levenshtein_similarity(text1, text2)
        seq = TextProcessor.compute_sequence_similarity(text1, text2)

        combined = tri * trigram_weight + lev * levenshtein_weight + seq * sequence_weight
        return min(1.0, combined)

    # ------------------------------------------------------------------
    # Invoice feature extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_invoice_features(text: str) -> Dict[str, Any]:
        """Extract structural features from invoice text for matching."""
        if not text:
            return {}

        features: Dict[str, Any] = {}

        numbers = re.findall(r"\d+", text)
        features["number_count"] = len(numbers)
        features["number_sequence"] = " ".join(numbers[:10])

        date_patterns = re.findall(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", text)
        features["date_count"] = len(date_patterns)
        features["date_sequence"] = " ".join(date_patterns[:5])

        amount_patterns = re.findall(r"\$?\d+[,.]?\d+\.?\d{2}", text)
        features["amount_count"] = len(amount_patterns)
        features["amount_sequence"] = " ".join(amount_patterns[:5])

        vendor_indicators = {"vendor", "supplier", "company", "inc", "corp", "llc", "ltd"}
        features["vendor_indicators"] = sum(
            1 for ind in vendor_indicators if ind in text.lower()
        )

        line_item_patterns = [
            r"item\s*\d+",
            r"line\s*\d+",
            r"product\s*\d+",
            r"qty\.?\s*\d+",
        ]
        features["line_item_hints"] = sum(
            len(re.findall(p, text, re.IGNORECASE)) for p in line_item_patterns
        )

        return features
