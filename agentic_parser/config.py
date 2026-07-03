"""Model registry — mapping tool → model.

Biar gampang: setiap tool pakai model sendiri-sendiri.
Yang ringan cukup pakai 3.1 (irit token, rate limit longgar),
yang butuh akurasi pakai 3.3.

Edit bebas sesuai kebutuhan token budget.
"""

# ── Model per tool ──────────────────────────────────────────────────

REASONING_MODEL = "llama-3.1-8b-instant"
"""Model untuk reasoning loop — cuma decision making, irit token."""

HEADER_MODEL = "openai/gpt-oss-120b"
"""Model untuk extract_header_fields — butuh akurasi parsing field."""

PELAKSANA_MODEL = "openai/gpt-oss-120b"
"""Model untuk extract_pelaksana — butuh akurasi ekstrak nama."""

CONTENT_MODEL = "openai/gpt-oss-120b"
"""Model untuk generate_laporan_content — narasi, perlu kreativitas."""

# ── Batch configuration ─────────────────────────────────────────────

MODEL_FOR_TOOL = {
    "extract_header_fields": HEADER_MODEL,
    "extract_pelaksana": PELAKSANA_MODEL,
    "generate_laporan_content": CONTENT_MODEL,
    # validate_completeness — pure Python, no LLM call
}

# ── Loop config ─────────────────────────────────────────────────────

MAX_ITERATIONS = 5
"""Maksimal iterasi reasoning loop sebelum fallback."""

# ── Tips ───────────────────────────────────────────────────────────
# Mau hemat token? Ganti CONTENT_MODEL ke 3.1, parsing tetap 3.3.
# Mau maksimal irit? Ganti HEADER_MODEL & PELAKSANA_MODEL juga.
