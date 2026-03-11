"""
Contact info extractor – detect phone numbers, email, addresses, opening hours.
"""
import re
from typing import List

from .chunker import Chunk


_PHONE_RE = re.compile(r"(?:\+31|0)\s*[\d\s\-().]{7,15}")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_HOURS_RE = re.compile(
    r"(?:ma(?:andag)?|di(?:nsdag)?|wo(?:ensdag)?|do(?:nderdag)?|vr(?:ijdag)?|za(?:terdag)?|zo(?:ndag)?)"
    r"[\s\-:]+\d{1,2}[.:]\d{2}",
    re.I,
)
_POSTCODE_RE = re.compile(r"\b\d{4}\s?[A-Z]{2}\b")


def extract_contact_chunks(
    text: str,
    heading_hierarchy: list[str] | None = None,
) -> List[Chunk]:
    """Extract contact info as a dedicated chunk with structured metadata."""
    hierarchy = heading_hierarchy or []

    phones = _PHONE_RE.findall(text)
    emails = _EMAIL_RE.findall(text)
    hours = _HOURS_RE.findall(text)
    postcodes = _POSTCODE_RE.findall(text)

    signal_count = len(phones) + len(emails) + len(hours) + len(postcodes)
    if signal_count < 1:
        return []

    meta = {}
    if phones:
        meta["phones"] = [p.strip() for p in phones]
    if emails:
        meta["emails"] = emails
    if hours:
        meta["opening_hours"] = hours
    if postcodes:
        meta["postcodes"] = postcodes

    return [Chunk(
        content=text.strip(),
        chunk_type="contact",
        section_path=" > ".join(hierarchy + ["Contact"]) if hierarchy else "Contact",
        heading_hierarchy=hierarchy,
        metadata=meta,
    )]
