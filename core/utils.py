"""Shared utilities for LaPeraN — single source of truth for helpers."""

import re


def normalize_waktu(raw: str) -> str:
    """Strip descriptive time words (pagi, sore, WIB, dll), keep only HH:MM."""
    if not raw or raw.strip().lower() == "selesai":
        return raw
    m = re.search(r'(\d{1,2})[.:](\d{2})', raw)
    if m:
        return f"{m.group(1).zfill(2)}:{m.group(2)}"
    return raw


def sanitize_konteks(raw: str | None, max_len: int = 2000) -> str | None:
    """Sanitize user-provided konteks_hasil input.

    - Strips leading/trailing whitespace
    - Removes control characters (except newlines/tabs)
    - Enforces max length
    - Returns None if empty after sanitization
    """
    if not raw or not isinstance(raw, str):
        return None
    # Remove control chars except \n \t \r
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw)
    cleaned = cleaned.strip()
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned
