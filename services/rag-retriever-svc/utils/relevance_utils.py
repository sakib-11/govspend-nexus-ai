"""Relevance utilities — score normalisation, combining, and confidence."""

from __future__ import annotations

from typing import Dict, List, Tuple


def normalise_scores(scores: List[float]) -> List[float]:
    """Min-max normalise *scores* to [0, 1].

    Returns a list of 0.5 for all entries when all scores are equal.
    """
    if not scores:
        return []
    lo = min(scores)
    hi = max(scores)
    if hi == lo:
        return [0.5] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


def combine_dense_sparse(
    dense_scores: Dict[str, float],
    sparse_scores: Dict[str, float],
    dense_weight: float = 0.7,
    sparse_weight: float = 0.3,
) -> Dict[str, float]:
    """Combine normalised dense and sparse scores per chunk_id.

    Chunks found by only one retriever receive that retriever's weighted
    score; chunks found by both receive the weighted sum.
    """
    all_ids = set(dense_scores) | set(sparse_scores)
    combined: Dict[str, float] = {}
    for cid in all_ids:
        d = dense_scores.get(cid, 0.0)
        s = sparse_scores.get(cid, 0.0)
        combined[cid] = dense_weight * d + sparse_weight * s
    return combined


def compute_relevance_confidence(
    similarity: float,
    dense_score: float | None = None,
    sparse_score: float | None = None,
    rerank_score: float | None = None,
) -> float:
    """Compute a combined confidence score in [0, 1].

    If a rerank score is available it dominates; otherwise a weighted
    blend of dense and sparse scores is used.
    """
    if rerank_score is not None:
        return max(0.0, min(1.0, rerank_score))

    parts = [similarity]
    weights = [1.0]
    if dense_score is not None:
        parts.append(dense_score)
        weights.append(0.5)
    if sparse_score is not None:
        parts.append(sparse_score)
        weights.append(0.3)

    total_w = sum(weights)
    return max(0.0, min(1.0, sum(p * w for p, w in zip(parts, weights)) / total_w))


def rank_results(
    results: List[Tuple[str, float]], top_k: int = 10,
) -> List[Tuple[str, float]]:
    """Sort *(chunk_id, score)* pairs descending and return top_k."""
    return sorted(results, key=lambda x: x[1], reverse=True)[:top_k]
