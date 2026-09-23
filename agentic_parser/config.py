"""Model registry — mapping tool → model.

Preset-based: user pilih preset dari dropdown, semua model otomatis ter-assign.
Mau custom per-tool? Edit di bawah atau bikin preset baru.
"""

# ── Available presets (dropdown options) ────────────────────────────

AVAILABLE_MODELS = {
    "qwen/qwen3.6-27b": {
        "label": "Qwen 3.6 27B (Recommended)",
        "reasoning": "qwen/qwen3.6-27b",
        "header": "qwen/qwen3.6-27b",
        "pelaksana": "qwen/qwen3.6-27b",
        "content": "qwen/qwen3.6-27b",
    },
    "openai/gpt-oss-120b": {
        "label": "GPT-OSS 120B (Most Capable)",
        "reasoning": "openai/gpt-oss-120b",
        "header": "openai/gpt-oss-120b",
        "pelaksana": "openai/gpt-oss-120b",
        "content": "openai/gpt-oss-120b",
    },
    "openai/gpt-oss-20b": {
        "label": "GPT-OSS 20B (Fastest + Vision)",
        "reasoning": "openai/gpt-oss-20b",
        "header": "openai/gpt-oss-20b",
        "pelaksana": "openai/gpt-oss-20b",
        "content": "openai/gpt-oss-20b",
    },
    "meta-llama/llama-4-scout-17b-16e-instruct": {
        "label": "Llama 4 Scout",
        "reasoning": "meta-llama/llama-4-scout-17b-16e-instruct",
        "header": "meta-llama/llama-4-scout-17b-16e-instruct",
        "pelaksana": "meta-llama/llama-4-scout-17b-16e-instruct",
        "content": "meta-llama/llama-4-scout-17b-16e-instruct",
    },
    "deepseek-r1-distill-llama-70b": {
        "label": "DeepSeek R1 70B (Reasoning)",
        "reasoning": "deepseek-r1-distill-llama-70b",
        "header": "deepseek-r1-distill-llama-70b",
        "pelaksana": "deepseek-r1-distill-llama-70b",
        "content": "deepseek-r1-distill-llama-70b",
    },
}

DEFAULT_MODEL = "qwen/qwen3.6-27b"

# ── Active model assignment (set by web UI or override) ────────────

def get_model_config(model_key: str | None = None) -> dict:
    """Return model mapping untuk preset yang dipilih."""
    key = model_key or DEFAULT_MODEL
    return AVAILABLE_MODELS.get(key, AVAILABLE_MODELS[DEFAULT_MODEL])


# ── Legacy single-model vars (untuk backward compat) ───────────────

_default = get_model_config()
REASONING_MODEL = _default["reasoning"]
HEADER_MODEL = _default["header"]
PELAKSANA_MODEL = _default["pelaksana"]
CONTENT_MODEL = _default["content"]

MODEL_FOR_TOOL = {
    "extract_header_fields": HEADER_MODEL,
    "extract_pelaksana": PELAKSANA_MODEL,
    "generate_laporan_content": CONTENT_MODEL,
}

# ── Loop config ─────────────────────────────────────────────────────

MAX_ITERATIONS = 5
"""Maksimal iterasi reasoning loop sebelum fallback."""
