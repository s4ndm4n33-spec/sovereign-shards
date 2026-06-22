"""Topic clustering, timeline grouping, and cross-conversation extraction.

Extraction is rule-based and deterministic — no LLM calls, no network.
Patterns were tuned for common phrasings found in AI chat transcripts
("decided to…", "fixed the bug by…", "should we…?", etc.).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Iterable

from .models import Conversation

# ---------------------------------------------------------------------------
# Keyword clustering
# ---------------------------------------------------------------------------

_STOPWORDS = set(
    """
    a about above after again against all am an and any are aren't as at be because
    been before being below between both but by can't cannot could couldn't did didn't
    do does doesn't doing don't down during each few for from further had hadn't has
    hasn't have haven't having he he'd he'll he's her here here's hers herself him himself
    his how how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more
    most mustn't my myself no nor not of off on once only or other ought our ours ourselves
    out over own same shan't she she'd she'll she's should shouldn't so some such than
    that that's the their theirs them themselves then there there's these they they'd they'll
    they're they've this those through to too under until up very was wasn't we we'd we'll
    we're we've were weren't what what's when when's where where's which while who who's whom
    why why's with won't would wouldn't you you'd you'll you're you've your yours yourself
    yourselves the a an and or but if then else for to of in on at by with from as is it
    this that these those i you he she we they me him her us them my your his hers our their
    """.split()
)

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")


def _tokenize(text: str) -> list[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 2]


def _conversation_keywords(conv: Conversation, top_k: int = 8) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for m in conv.messages:
        for tok in _tokenize(m.content):
            counter[tok] += 1
    return counter.most_common(top_k)


def cluster_conversations(conversations: list[Conversation], num_clusters: int = 0) -> list[list[Conversation]]:
    """Group conversations by shared dominant keywords.

    Uses a simple leader-follower greedy assignment: each conversation
    joins the first existing cluster with sufficient keyword overlap, or
    starts a new one. Deterministic and O(n*clusters).
    """
    if not conversations:
        return []
    features = {id(c): set(w for w, _ in _conversation_keywords(c)) for c in conversations}

    # Sort by date for deterministic clustering
    ordered = sorted(conversations, key=lambda c: c.created or datetime.min)
    clusters: list[list[Conversation]] = []
    cluster_keywords: list[set[str]] = []

    for conv in ordered:
        kw = features[id(conv)]
        placed = False
        for idx, ckw in enumerate(cluster_keywords):
            if ckw and kw:
                overlap = len(kw & ckw)
                # Require at least 2 shared keywords, or 50% of smaller set
                if overlap >= 2 or (overlap / max(1, min(len(kw), len(ckw))) >= 0.5):
                    clusters[idx].append(conv)
                    ckw |= kw
                    placed = True
                    break
        if not placed:
            clusters.append([conv])
            cluster_keywords.append(set(kw))

    # Sort clusters by earliest date
    def _earliest(cluster: list[Conversation]) -> datetime:
        dates = [c.created for c in cluster if c.created]
        return min(dates) if dates else datetime.min

    clusters.sort(key=_earliest)
    return clusters


def group_by_project(conversations: list[Conversation]) -> dict[str, list[Conversation]]:
    """Assign each conversation to a project label derived from clustering.

    The project label is the top shared keyword (or 'misc') so the UI can
    show coarse groupings without requiring the user to tag anything.
    """
    clusters = cluster_conversations(conversations)
    groups: dict[str, list[Conversation]] = defaultdict(list)
    for idx, cluster in enumerate(clusters):
        if not cluster:
            continue
        # Project label = most common keyword across the cluster
        counter: Counter[str] = Counter()
        for c in cluster:
            for w, n in _conversation_keywords(c):
                counter[w] += n
        label = counter.most_common(1)[0][0] if counter else "misc"
        groups[label].extend(cluster)
    return dict(groups)


# ---------------------------------------------------------------------------
# Timeline ordering
# ---------------------------------------------------------------------------

def timeline(conversations: list[Conversation]) -> list[Conversation]:
    return sorted(conversations, key=lambda c: c.created or c.updated or datetime.min)


# ---------------------------------------------------------------------------
# Extraction patterns
# ---------------------------------------------------------------------------

# Each entry: (label, compiled regex, min_len, max_len)
_DECISION_RE = re.compile(
    r"\b(?:decided|decision|chose|choosing|chosen|adopted|agreed|concluded|opted|settled on|committed to|we'll use|we will use|going with|sticking with)\b",
    re.IGNORECASE,
)

_PROBLEM_RE = re.compile(
    r"\b(?:bug|error|broken|failing|failed|failure|crash|crash|issue|problem|doesn't work|doesn't work|does not work|not working|exception|traceback|raised|threw|wrong|incorrect|unexpected|oops|hangs|hanging|deadlock|regression)\b",
    re.IGNORECASE,
)

_SOLUTION_RE = re.compile(
    r"\b(?:fixed|fixes|fixing|resolved|solved|solution|workaround|patched|corrected|changed to|updated to|replaced with|swapped to|switched to|now uses|now using)\b",
    re.IGNORECASE,
)

_ARCH_RE = re.compile(
    r"\b(?:architecture|refactor|refactoring|restructured|moved to|migrated to|introduced|added a layer|abstraction|module|component|service|pipeline|plugin|interface|contract|schema|migration|data model|data flow|layered)\b",
    re.IGNORECASE,
)

_QUESTION_RE = re.compile(
    r"\b(?:should we|how should|what if|can we|could we|do we need|is it worth|question|wondering|unclear|not sure|unsure|open question|tbd|todo|follow[- ]?up)\b",
    re.IGNORECASE,
)

_THEME_CANDIDATES = (
    "auth", "database", "ui", "frontend", "backend", "api", "performance",
    "testing", "security", "deploy", "deployment", "docker", "ci", "config",
    "state", "render", "cache", "async", "stream", "model", "prompt",
    "tool", "agent", "memory", "vector", "embed", "rag", "token", "cost",
)


def _extract_sentences(text: str) -> list[str]:
    # Lightweight sentence splitter — robust enough for transcripts.
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 15]


def _matches(sentences: list[str], pattern: re.Pattern, limit: int = 8) -> list[str]:
    hits: list[str] = []
    seen: set[str] = set()
    for s in sentences:
        if pattern.search(s):
            key = s.lower()[:120]
            if key in seen:
                continue
            seen.add(key)
            hits.append(s)
            if len(hits) >= limit:
                break
    return hits


def extract_from_conversation(conv: Conversation) -> dict:
    text = conv.full_text()
    sentences = _extract_sentences(text)
    return {
        "decisions": _matches(sentences, _DECISION_RE),
        "bugs": _matches(sentences, _PROBLEM_RE),
        "fixes": _matches(sentences, _SOLUTION_RE),
        "architecture": _matches(sentences, _ARCH_RE),
        "open_questions": _matches(sentences, _QUESTION_RE),
    }


def extract_themes(conversations: list[Conversation], top_k: int = 10) -> list[tuple[str, int]]:
    """Return the most frequent technical keywords across all conversations."""
    counter: Counter[str] = Counter()
    for c in conversations:
        for m in c.messages:
            for tok in _tokenize(m.content):
                if tok in _THEME_CANDIDATES or any(cand in tok for cand in _THEME_CANDIDATES):
                    counter[tok] += 1
    return counter.most_common(top_k)


# ---------------------------------------------------------------------------
# Summarization (rule-based extractive)
# ---------------------------------------------------------------------------

def summarize(conv: Conversation, max_sentences: int = 2) -> str:
    """Produce a one-paragraph cliffnotes summary via extractive ranking.

    Scores sentences by keyword frequency, picks the top N, and returns
    them joined into a paragraph. Deterministic; no LLM required.
    """
    text = conv.full_text()
    if not text:
        return "(empty conversation)"
    sentences = _extract_sentences(text)
    if not sentences:
        return text[:240].strip()

    # Score by overlap with the conversation's top keywords
    kw = {w for w, _ in _conversation_keywords(conv, top_k=10)}
    if not kw:
        return sentences[0]

    scored: list[tuple[float, int, str]] = []
    for i, s in enumerate(sentences):
        toks = set(_tokenize(s))
        score = len(toks & kw) / max(1, len(toks)) if toks else 0.0
        # Slight positional bias toward early sentences ( intros carry context)
        score += 0.01 * (1.0 - min(i, 20) / 20.0)
        scored.append((score, i, s))
    scored.sort(key=lambda t: (-t[0], t[1]))
    chosen = sorted(scored[:max_sentences], key=lambda t: t[1])
    summary = " ".join(s for _, _, s in chosen)
    if len(summary) > 320:
        summary = summary[:317].rstrip() + "…"
    return summary
