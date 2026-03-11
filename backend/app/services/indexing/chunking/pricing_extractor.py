"""
Pricing extractor – detect plan names, prices, and features; produce pricing chunks.
"""
import re
from typing import List

from .chunker import Chunk


_PRICE_RE = re.compile(r"€\s*\d+[\d.,]*|(?:\d+[\d.,]*)\s*(?:euro|EUR)", re.I)
_PER_PERIOD_RE = re.compile(r"per\s+(?:maand|jaar|month|year)|/\s*(?:mo|yr|maand|jaar)", re.I)

# Common plan name patterns
_PLAN_NAME_RE = re.compile(
    r"\b(starter|basic|standaard|standard|business|professional|pro|premium|enterprise|gratis|free|plus|growth)\b",
    re.I,
)


def extract_pricing_chunks(
    text: str,
    heading_hierarchy: list[str] | None = None,
) -> List[Chunk]:
    """Extract pricing plan information as individual chunks."""
    chunks: List[Chunk] = []
    hierarchy = heading_hierarchy or []

    sections = _split_pricing_sections(text)

    for section in sections:
        prices = _PRICE_RE.findall(section["body"])
        if not prices:
            continue

        plan_names = _PLAN_NAME_RE.findall(section["heading"] + " " + section["body"])
        plan_name = plan_names[0] if plan_names else "Onbekend plan"

        features = _extract_features(section["body"])

        meta = {
            "plan_name": plan_name,
            "prices": prices,
        }
        if features:
            meta["features"] = features

        chunks.append(Chunk(
            content=section["body"].strip(),
            chunk_type="pricing",
            section_path=" > ".join(hierarchy + ["Pricing", plan_name]) if hierarchy else f"Pricing > {plan_name}",
            heading_hierarchy=hierarchy + [plan_name],
            metadata=meta,
        ))

    return chunks


def _split_pricing_sections(text: str) -> list[dict]:
    """Split pricing text into per-plan sections based on headings or price blocks."""
    sections = []
    parts = re.split(r"(?=^#{1,4}\s)", text, flags=re.MULTILINE)

    for part in parts:
        part = part.strip()
        if not part:
            continue
        heading_match = re.match(r"^#{1,4}\s+(.+)", part)
        heading = heading_match.group(1).strip() if heading_match else ""
        body = part[heading_match.end():].strip() if heading_match else part
        if _PRICE_RE.search(body) or _PRICE_RE.search(heading):
            sections.append({"heading": heading, "body": f"{heading}\n{body}" if heading else body})

    # If no heading-based sections, treat full text as one section
    if not sections and _PRICE_RE.search(text):
        sections.append({"heading": "", "body": text})

    return sections


def _extract_features(text: str) -> list[str]:
    """Extract feature list items from pricing text."""
    features = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- ") or line.startswith("✓") or line.startswith("•"):
            features.append(line.lstrip("-✓• ").strip())
    return features[:20]
