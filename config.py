import os
import tempfile
import base64
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Baca .env manual — zero dependency
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# Write template from base64 string to a temp file (bypasses HF git binary restrictions)
from templates.template_data import TEMPLATE_B64
_tmp_dir = Path(tempfile.gettempdir())
TEMPLATE_PATH = _tmp_dir / "template_laporan.docx"
TEMPLATE_PATH.write_bytes(base64.b64decode(TEMPLATE_B64))

