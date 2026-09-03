"""Text utilities — query cleaning, tokenization, and text processing."""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional


# Common English stop words (minimal set — avoids NLTK dependency)
_STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "was", "are", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "dare",
    "ought", "used", "it", "its", "this", "that", "these", "those",
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "they", "them", "their", "theirs", "themselves",
    "what", "which", "who", "whom", "when", "where", "why", "how",
    "not", "no", "nor", "so", "than", "too", "very", "just",
    "about", "above", "after", "again", "all", "also", "any", "because",
    "before", "below", "between", "both", "each", "few", "more", "most",
    "other", "some", "such", "only", "own", "same", "then", "there",
    "through", "under", "until", "up", "while",
})

# Domain-specific terms to KEEP even though they appear in stop-word lists
_DOMAIN_KEEP: frozenset[str] = frozenset({
    "procurement", "contract", "vendor", "invoice", "payment",
    "audit", "fraud", "compliance", "regulation", "policy",
    "government", "financial", "report", "transaction", "anomaly",
    "duplicate", "price", "cost", "supplier", "official",
})


def clean_query(query: str) -> str:
    """Clean and normalise a query string.

    - Strips Unicode noise
    - Removes special characters (keeps alphanumerics, spaces, basic punctuation)
    - Collapses whitespace
    - Lowercases
    """
    # Normalise Unicode
    query = unicodedata.normalize("NFKD", query)
    # Remove special characters
    query = re.sub(r"[^\w\s.,;!?\"'-]", " ", query)
    # Collapse whitespace
    query = " ".join(query.split())
    return query.lower().strip()


def tokenize(text: str, *, remove_stop_words: bool = True) -> List[str]:
    """Tokenize *text* into words, optionally removing stop words.

    Domain-specific terms are always kept.
    """
    tokens = re.findall(r"\b\w+\b", text.lower())
    if not remove_stop_words:
        return tokens
    return [
        t for t in tokens
        if t not in _STOP_WORDS or t in _DOMAIN_KEEP
    ]


def stem_tokens(tokens: List[str]) -> List[str]:
    """Apply simple suffix stripping (minimal stemmer — no NLTK needed)."""
    stems: List[str] = []
    for token in tokens:
        if len(token) <= 3:
            stems.append(token)
            continue
        # Very basic English suffix stripping
        for suffix in ("ing", "tion", "ness", "ment", "able", "ible", "ful", "less", "ous", "ive", "ly", "ed", "er", "es", "s"):
            if token.endswith(suffix) and len(token) - len(suffix) >= 3:
                stems.append(token[: -len(suffix)])
                break
        else:
            stems.append(token)
    return stems


def extract_key_phrases(text: str, min_words: int = 2, max_words: int = 3) -> List[str]:
    """Extract n-gram key phrases from *text*."""
    words = text.split()
    phrases: List[str] = []
    for n in range(min_words, max_words + 1):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i : i + n])
            if len(phrase) >= 8:  # only meaningful phrases
                phrases.append(phrase)
    return list(dict.fromkeys(phrases))  # dedupe preserving order


def build_search_vector(query: str) -> str:
    """Build a PostgreSQL ``tsquery`` string from *query*.

    Each word gets a ``:*`` prefix-match suffix and words are joined with
    ``&`` (AND).
    """
    words = re.sub(r"[^\w\s]", " ", query).split()
    weighted = [f"{w}:*" for w in words if len(w) > 2]
    return " & ".join(weighted) if weighted else ""


def truncate(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate *text* to *max_length* characters."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
