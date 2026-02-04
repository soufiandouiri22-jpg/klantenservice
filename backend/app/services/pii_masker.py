"""
klantenservice.ai - PII Masking Utility

Masks personally identifiable information in text for logging/display.
"""
import re
from typing import Optional


def mask_phone(text: str) -> str:
    """
    Mask phone numbers in text.
    
    Examples:
    - 06-12345678 -> 06-****5678
    - +31612345678 -> +316****5678
    - 0612345678 -> 06****5678
    """
    # Dutch mobile numbers
    text = re.sub(
        r'(06[\s-]?)(\d{4})(\d{4})',
        r'\1****\3',
        text
    )
    
    # International format
    text = re.sub(
        r'(\+31\s?6)(\d{4})(\d{4})',
        r'\1****\3',
        text
    )
    
    # General phone pattern (keep first 3 and last 4 digits)
    text = re.sub(
        r'(\d{2,3})[\s-]?(\d{3,4})[\s-]?(\d{4})',
        lambda m: f"{m.group(1)}{'*' * len(m.group(2))}{m.group(3)}",
        text
    )
    
    return text


def mask_email(text: str) -> str:
    """
    Mask email addresses in text.
    
    Examples:
    - jan@example.com -> j**@example.com
    - johndoe@gmail.com -> joh***@gmail.com
    """
    def mask_email_match(match):
        email = match.group(0)
        local, domain = email.split('@')
        if len(local) <= 2:
            masked_local = local[0] + '*'
        else:
            visible = min(3, len(local) // 2)
            masked_local = local[:visible] + '*' * (len(local) - visible)
        return f"{masked_local}@{domain}"
    
    # Email pattern
    text = re.sub(
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        mask_email_match,
        text
    )
    
    return text


def mask_address(text: str) -> str:
    """
    Mask street addresses in text.
    
    Masks house numbers and postal codes.
    """
    # Dutch postal codes (1234 AB)
    text = re.sub(
        r'(\d{4})\s*([A-Z]{2})',
        r'**** **',
        text
    )
    
    # House numbers (straatnaam 123a -> straatnaam ***)
    text = re.sub(
        r'(\b[A-Za-z]+(?:straat|weg|laan|plein|singel|kade|gracht)\s+)(\d+[a-zA-Z]?)',
        r'\1***',
        text,
        flags=re.IGNORECASE
    )
    
    return text


def mask_name(text: str, names_to_mask: list[str] = None) -> str:
    """
    Mask specific names in text.
    
    Args:
        text: The text to mask
        names_to_mask: List of names to mask (case-insensitive)
    """
    if not names_to_mask:
        return text
    
    for name in names_to_mask:
        if len(name) > 1:
            # Keep first letter, mask the rest
            masked = name[0] + '*' * (len(name) - 1)
            text = re.sub(
                re.escape(name),
                masked,
                text,
                flags=re.IGNORECASE
            )
    
    return text


def mask_iban(text: str) -> str:
    """
    Mask IBAN numbers in text.
    
    Example:
    - NL91ABNA0417164300 -> NL91****4300
    """
    text = re.sub(
        r'([A-Z]{2}\d{2})([A-Z]{4})(\d{6})(\d{4})',
        r'\1********\4',
        text
    )
    return text


def mask_bsn(text: str) -> str:
    """
    Mask Dutch BSN (citizen service number) in text.
    
    Example:
    - 123456789 -> ***456***
    """
    # BSN is 8-9 digits, often written with dots
    text = re.sub(
        r'\b(\d{3})\.?(\d{3})\.?(\d{2,3})\b',
        r'***.\2.***',
        text
    )
    return text


def mask_pii(
    text: str,
    mask_phones: bool = True,
    mask_emails: bool = True,
    mask_addresses: bool = True,
    mask_ibans: bool = True,
    mask_bsns: bool = True,
    names_to_mask: Optional[list[str]] = None
) -> str:
    """
    Apply all PII masking to text.
    
    Args:
        text: The text to mask
        mask_phones: Mask phone numbers
        mask_emails: Mask email addresses
        mask_addresses: Mask street addresses
        mask_ibans: Mask IBAN numbers
        mask_bsns: Mask BSN numbers
        names_to_mask: Specific names to mask
        
    Returns:
        Text with PII masked
    """
    if not text:
        return text
    
    if mask_phones:
        text = mask_phone(text)
    
    if mask_emails:
        text = mask_email(text)
    
    if mask_addresses:
        text = mask_address(text)
    
    if mask_ibans:
        text = mask_iban(text)
    
    if mask_bsns:
        text = mask_bsn(text)
    
    if names_to_mask:
        text = mask_name(text, names_to_mask)
    
    return text


# Convenience function with default settings
def mask_transcript(text: str, customer_name: Optional[str] = None) -> str:
    """
    Mask PII in a transcript with standard settings.
    
    Args:
        text: Transcript text
        customer_name: Customer's name to also mask
        
    Returns:
        Masked transcript
    """
    names = [customer_name] if customer_name else None
    return mask_pii(text, names_to_mask=names)
