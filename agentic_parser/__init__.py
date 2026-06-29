"""Agentic parser — standalone module, terpisah dari core/.

Usage (signature sama dengan core.ai_parser.parse_surat_tugas):
    from agentic_parser import parse_surat_tugas
    laporan = parse_surat_tugas(teks_pdf, api_key)
"""

from .loop import parse_surat_tugas

__all__ = ["parse_surat_tugas"]
