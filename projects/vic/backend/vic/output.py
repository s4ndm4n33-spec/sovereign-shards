"""Output writers for V.I.C.: JSONL archive and PDF report."""

from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .extract import extract_from_conversation, extract_themes, summarize, timeline
from .models import Conversation


# ---------------------------------------------------------------------------
# JSONL archive — one entry per session
# ---------------------------------------------------------------------------

def build_jsonl(conversations: list[Conversation]) -> str:
    """Return archive.jsonl text, one structured entry per session."""
    ordered = timeline(conversations)
    lines: list[str] = []
    for idx, conv in enumerate(ordered, start=1):
        ext = extract_from_conversation(conv)
        entry = {
            "session": idx,
            "date": conv.date_iso(),
            "provider": conv.provider,
            "summary": summarize(conv),
            "decisions": ext["decisions"],
            "bugs": ext["bugs"],
            "fixes": ext["fixes"],
            "open_questions": ext["open_questions"],
        }
        lines.append(json.dumps(entry, ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")


def parse_jsonl(text: str) -> list[dict]:
    """Parse archive.jsonl back into entries for preview/inspection."""
    entries: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


# ---------------------------------------------------------------------------
# PDF report (reportlab)
# ---------------------------------------------------------------------------

PROVIDER_LABEL = {
    "gemini": "Gemini",
    "chatgpt": "ChatGPT",
    "claude": "Claude",
    "unknown": "Unknown",
}


def _date_range(conversations: list[Conversation]) -> tuple[str, str]:
    dates = [c.created for c in conversations if c.created]
    if not dates:
        dates = [c.updated for c in conversations if c.updated]
    if not dates:
        return ("unknown", "unknown")
    return (min(dates).strftime("%Y-%m-%d"), max(dates).strftime("%Y-%m-%d"))


def _executive_summary(conversations: list[Conversation], themes: list[tuple[str, int]]) -> str:
    providers = sorted({c.provider for c in conversations})
    start, end = _date_range(conversations)
    prov_list = ", ".join(PROVIDER_LABEL.get(p, p.title()) for p in providers)
    theme_str = "; ".join(f"{t} ({n})" for t, n in themes[:6]) if themes else "none detected"
    total_msgs = sum(len(c.messages) for c in conversations)
    return (
        f"Archive spans {len(conversations)} conversations across {len(providers)} "
        f"provider(s): {prov_list}. Date range: {start} to {end}. "
        f"Approximately {total_msgs} messages analyzed. "
        f"Recurring themes: {theme_str}."
    )


def build_pdf(conversations: list[Conversation], project_title: str = "AI Chat Archive") -> bytes:
    """Generate the structured PDF report and return bytes."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            PageBreak,
            ListFlowable,
            ListItem,
        )
    except ImportError as exc:
        raise RuntimeError("reportlab is required for PDF generation") from exc

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.8 * inch,
        bottomMargin=0.8 * inch,
        title=project_title,
    )

    styles = getSampleStyleSheet()
    body_style = ParagraphStyle("VicBody", parent=styles["Normal"], fontSize=10, leading=14, alignment=TA_LEFT)
    h1_style = ParagraphStyle("VicH1", parent=styles["Heading1"], fontSize=18, spaceAfter=12, textColor=colors.HexColor("#0F172A"))
    h2_style = ParagraphStyle("VicH2", parent=styles["Heading2"], fontSize=13, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor("#1E3A8A"))
    small_style = ParagraphStyle("VicSmall", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#475569"))

    ordered = timeline(conversations)
    themes = extract_themes(ordered)
    start, end = _date_range(ordered)
    providers = sorted({c.provider for c in ordered})

    story: list = []

    # Title block
    story.append(Paragraph(project_title, h1_style))
    story.append(Paragraph(f"Date range: {start} – {end}", small_style))
    story.append(Paragraph(
        "Providers: " + (", ".join(PROVIDER_LABEL.get(p, p.title()) for p in providers) or "none"),
        small_style,
    ))
    story.append(Paragraph(f"Sessions analyzed: {len(ordered)}", small_style))
    story.append(Spacer(1, 0.2 * inch))

    # Executive summary
    story.append(Paragraph("Executive Summary", h2_style))
    story.append(Paragraph(_executive_summary(ordered, themes), body_style))
    story.append(Spacer(1, 0.15 * inch))

    # Key decisions (dated)
    story.append(Paragraph("Key Decisions", h2_style))
    decisions_all: list[tuple[str, str]] = []  # (date, text)
    for conv in ordered:
        ext = extract_from_conversation(conv)
        for d in ext["decisions"]:
            decisions_all.append((conv.date_iso(), d))
    if decisions_all:
        items = [ListItem(Paragraph(f"<b>{d}</b> — {t}", body_style), value=None) for d, t in decisions_all[:40]]
        story.append(ListFlowable(items, bulletType="bullet"))
    else:
        story.append(Paragraph("No explicit decisions detected.", small_style))
    story.append(Spacer(1, 0.15 * inch))

    # Problems and resolutions
    story.append(Paragraph("Problems and Resolutions", h2_style))
    problem_pairs: list[tuple[str, str, str]] = []
    for conv in ordered:
        ext = extract_from_conversation(conv)
        for b in ext["bugs"][:3]:
            problem_pairs.append((conv.date_iso(), b, ""))
        for f in ext["fixes"][:3]:
            problem_pairs.append((conv.date_iso(), "", f))
    if problem_pairs:
        items = []
        for d, bug, fix in problem_pairs[:40]:
            if bug:
                items.append(ListItem(Paragraph(f"<b>{d}</b> [BUG] {bug}", body_style)))
            if fix:
                items.append(ListItem(Paragraph(f"<b>{d}</b> [FIX] {fix}", body_style)))
        story.append(ListFlowable(items, bulletType="bullet"))
    else:
        story.append(Paragraph("No problems detected.", small_style))
    story.append(Spacer(1, 0.15 * inch))

    # Architecture evolution
    story.append(Paragraph("Architecture Evolution", h2_style))
    arch_items = []
    for conv in ordered:
        ext = extract_from_conversation(conv)
        for a in ext["architecture"][:2]:
            arch_items.append((conv.date_iso(), a))
    if arch_items:
        items = [ListItem(Paragraph(f"<b>{d}</b> — {a}", body_style)) for d, a in arch_items[:30]]
        story.append(ListFlowable(items, bulletType="bullet"))
    else:
        story.append(Paragraph("No architectural changes detected.", small_style))
    story.append(Spacer(1, 0.15 * inch))

    # Open questions
    story.append(Paragraph("Open Questions", h2_style))
    qs: list[str] = []
    for conv in ordered:
        ext = extract_from_conversation(conv)
        qs.extend(ext["open_questions"][:2])
    if qs:
        items = [ListItem(Paragraph(q, body_style)) for q in qs[:30]]
        story.append(ListFlowable(items, bulletType="bullet"))
    else:
        story.append(Paragraph("No open questions detected.", small_style))
    story.append(Spacer(1, 0.15 * inch))

    # Recurring themes
    story.append(Paragraph("Recurring Themes", h2_style))
    if themes:
        theme_lines = [Paragraph(f"<b>{t}</b> — {n} mentions", body_style) for t, n in themes]
        for tl in theme_lines:
            story.append(tl)
    else:
        story.append(Paragraph("No recurring themes detected.", small_style))

    story.append(PageBreak())

    # Per-session cliffnotes
    story.append(Paragraph("Per-Session Cliffnotes", h2_style))
    for idx, conv in enumerate(ordered, start=1):
        title = (conv.title or "(untitled)")[:100]
        prov = PROVIDER_LABEL.get(conv.provider, conv.provider.title())
        story.append(Paragraph(
            f"Session {idx} — {conv.date_iso()} — {prov} — {title}",
            ParagraphStyle("VicSessionHead", parent=h2_style, fontSize=11, spaceBefore=10, textColor=colors.HexColor("#0F172A")),
        ))
        story.append(Paragraph(summarize(conv, max_sentences=3), body_style))
        ext = extract_from_conversation(conv)
        if ext["decisions"] or ext["bugs"] or ext["fixes"] or ext["open_questions"]:
            detail_lines: list[str] = []
            for d in ext["decisions"][:1]:
                detail_lines.append(f"Decision: {d}")
            for b in ext["bugs"][:1]:
                detail_lines.append(f"Problem: {b}")
            for f in ext["fixes"][:1]:
                detail_lines.append(f"Fix: {f}")
            for q in ext["open_questions"][:1]:
                detail_lines.append(f"Open: {q}")
            story.append(Paragraph("  • " + "  • ".join(detail_lines), small_style))
        story.append(Spacer(1, 0.1 * inch))

    doc.build(story)
    return buf.getvalue()
