"""Advanced text similarity service for document matching."""

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

from ..utils.logging import get_logger
from ..utils.text_processing import TextProcessor

logger = get_logger(__name__)

# Optional: TF-IDF cosine similarity
try:
    from sklearn.feature_extraction.text import TfidfVectorizer as _TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as _cosine_similarity

    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False


class TextSimilarityService:
    """Provides multiple text-similarity algorithms and a combined score.

    Algorithms available:
    * trigram (character 3-gram Jaccard)
    * Levenshtein normalised distance
    * word-level Jaccard
    * Ratcliff-Obershelp (SequenceMatcher)
    * TF-IDF cosine (requires scikit-learn)
    """

    def __init__(self) -> None:
        self.processor = TextProcessor()

    # ------------------------------------------------------------------
    # Individual algorithms
    # ------------------------------------------------------------------

    def trigram_similarity(self, text1: str, text2: str) -> float:
        """Character-trigram Jaccard similarity."""
        if not text1 or not text2:
            return 0.0

        t1 = self.processor.normalize_text(text1)
        t2 = self.processor.normalize_text(text2)

        tri1: Set[str] = {t1[i : i + 3] for i in range(len(t1) - 2)}
        tri2: Set[str] = {t2[i : i + 3] for i in range(len(t2) - 2)}
        if not tri1 or not tri2:
            return 0.0

        return len(tri1 & tri2) / len(tri1 | tri2)

    def compute_levenshtein_similarity(self, text1: str, text2: str) -> float:
        """Normalised Levenshtein similarity."""
        if not text1 or not text2:
            return 0.0

        t1 = self.processor.normalize_text(text1)
        t2 = self.processor.normalize_text(text2)

        from ..utils.text_processing import _lev_distance

        distance = _lev_distance(t1, t2)
        max_len = max(len(t1), len(t2))
        if max_len == 0:
            return 1.0
        return 1.0 - (distance / max_len)

    def jaccard_similarity(self, text1: str, text2: str) -> float:
        """Word-set Jaccard similarity."""
        if not text1 or not text2:
            return 0.0

        words1 = set(self.processor.tokenize(text1))
        words2 = set(self.processor.tokenize(text2))
        if not words1 or not words2:
            return 0.0

        return len(words1 & words2) / len(words1 | words2)

    def compute_sequence_similarity(self, text1: str, text2: str) -> float:
        """Ratcliff-Obershelp (SequenceMatcher) similarity."""
        if not text1 or not text2:
            return 0.0
        t1 = self.processor.normalize_text(text1)
        t2 = self.processor.normalize_text(text2)
        return SequenceMatcher(None, t1, t2).ratio()

    def cosine_similarity_tfidf(self, text1: str, text2: str) -> float:
        """TF-IDF cosine similarity (requires scikit-learn)."""
        if not _HAS_SKLEARN:
            return self.jaccard_similarity(text1, text2)

        if not text1 or not text2:
            return 0.0

        vectorizer = _TfidfVectorizer(
            max_features=1000,
            stop_words="english",
            ngram_range=(1, 2),
        )
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        return _cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

    # ------------------------------------------------------------------
    # Combined / weighted
    # ------------------------------------------------------------------

    def weighted_combined_similarity(
        self,
        text1: str,
        text2: str,
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Combine multiple similarity measures with configurable weights."""
        if not text1 or not text2:
            return 0.0

        default_weights = {
            "trigram": 0.35,
            "levenshtein": 0.25,
            "jaccard": 0.20,
            "sequence": 0.20,
        }
        weights = weights or default_weights

        methods = {
            "trigram": self.trigram_similarity,
            "levenshtein": self.compute_levenshtein_similarity,
            "jaccard": self.jaccard_similarity,
            "sequence": self.compute_sequence_similarity,
        }

        combined = sum(
            methods[name](text1, text2) * weight
            for name, weight in weights.items()
            if name in methods
        )
        return min(1.0, combined)

    # ------------------------------------------------------------------
    # Matching helpers
    # ------------------------------------------------------------------

    def find_best_matches(
        self,
        target: str,
        candidates: List[str],
        threshold: float = 0.6,
        max_results: int = 5,
    ) -> List[Tuple[str, float]]:
        """Return top matching candidates above *threshold*."""
        if not target or not candidates:
            return []

        scored = []
        for candidate in candidates:
            score = self.weighted_combined_similarity(target, candidate)
            if score >= threshold:
                scored.append((candidate, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:max_results]

    def extract_similarity_features(self, text: str) -> Dict[str, Any]:
        """Extract structural / statistical features for downstream use."""
        if not text:
            return {}

        features: Dict[str, Any] = {}
        features["length"] = len(text)
        features["word_count"] = len(text.split())
        features["unique_chars"] = len(set(text))
        features["digit_count"] = sum(1 for c in text if c.isdigit())
        features["alpha_count"] = sum(1 for c in text if c.isalpha())

        features["has_currency"] = bool(re.search(r"[$€£¥]", text))
        features["has_date"] = bool(re.search(r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}", text))
        features["has_number"] = bool(re.search(r"\d+", text))

        words = text.split()
        if words:
            features["avg_word_length"] = sum(len(w) for w in words) / len(words)
            features["unique_words_ratio"] = len(set(words)) / len(words)

        return features
