# Copyright (c) 2024-2026 Reed Richards (s4ndm4n33). Licensed under BSL 1.1.
"""BM25 retriever: pure Python, zero deps.

Scores memory chunks against a query using BM25 term weighting.
Works on working memory entries, knowledge base entries, or any
list of dicts with string values.
"""

from __future__ import annotations

import math
import re
from collections import Counter

# BM25 tuning parameters
K1 = 1.5
B = 0.75


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric + underscore tokenizer."""
    return re.findall(r"[a-z0-9_]+", text.lower())


def _idf(term: str, doc_freqs: dict[str, int], n_docs: int) -> float:
    df = doc_freqs.get(term, 0)
    return math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)


def _doc_text(chunk: dict) -> str:
    """Concatenate all string values in a chunk for scoring."""
    return " ".join(v for v in chunk.values() if isinstance(v, str))


def bm25_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    doc_freqs: dict[str, int],
    n_docs: int,
    avg_dl: float,
) -> float:
    tf = Counter(doc_tokens)
    dl = len(doc_tokens)
    score = 0.0
    for term in query_tokens:
        if term not in tf:
            continue
        idf = _idf(term, doc_freqs, n_docs)
        term_freq = tf[term]
        numerator = term_freq * (K1 + 1)
        denominator = term_freq + K1 * (1 - B + B * (dl / max(avg_dl, 1)))
        score += idf * (numerator / denominator)
    return score


def retrieve(
    query: str,
    chunks: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """Return top-K chunks most relevant to the query.

    Each chunk is a dict with string values used for scoring.
    Returns chunks sorted by relevance (highest first), '_score' added.
    """
    if not chunks or not query.strip():
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return chunks[:top_k]

    # Tokenize all docs and build document frequencies
    doc_token_lists: list[list[str]] = []
    doc_freqs: dict[str, int] = Counter()

    for chunk in chunks:
        tokens = tokenize(_doc_text(chunk))
        doc_token_lists.append(tokens)
        for term in set(tokens):
            doc_freqs[term] += 1

    n_docs = len(chunks)
    avg_dl = sum(len(t) for t in doc_token_lists) / max(n_docs, 1)

    scored: list[tuple[float, int, dict]] = []
    for i, chunk in enumerate(chunks):
        s = bm25_score(query_tokens, doc_token_lists[i], doc_freqs, n_docs, avg_dl)
        scored.append((s, i, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)

    results: list[dict] = []
    for s, _, chunk in scored[:top_k]:
        enriched = dict(chunk)
        enriched["_score"] = round(s, 3)
        results.append(enriched)
    return results
