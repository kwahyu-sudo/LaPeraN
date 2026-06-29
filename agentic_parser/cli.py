#!/usr/bin/env python3
"""CLI untuk test agentic parser — development only.

Usage:
    python -m agentic_parser.cli <path_surat_tugas.pdf>
    python -m agentic_parser.cli <path_surat_tugas.pdf> --render
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import GROQ_API_KEY, TEMPLATE_PATH
from core.pdf_extractor import extract_text_from_pdf, is_pdf_readable
from core.renderer import render_laporan
from agentic_parser import parse_surat_tugas

def main():
    parser = argparse.ArgumentParser(description="Test agentic parser")
    parser.add_argument("pdf_path", help="Path ke file PDF surat tugas")
    parser.add_argument("--render", action="store_true",
                        help="Render hasil ke .docx")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)

    if not pdf_path.exists():
        print(f"[ERROR] File tidak ditemukan: {pdf_path}")
        sys.exit(1)

    if not GROQ_API_KEY:
        print("[ERROR] GROQ_API_KEY tidak ditemukan.")
        sys.exit(1)

    print(f"[PDF] Membaca PDF: {pdf_path}")
    if not is_pdf_readable(str(pdf_path)):
        print("[ERROR] PDF tidak memiliki layer teks (scan).")
        sys.exit(1)

    print("[TXT] Mengekstrak teks...")
    teks = extract_text_from_pdf(str(pdf_path))

    print("\n[AI] Memanggil agentic parser...")
    try:
        laporan = parse_surat_tugas(teks, GROQ_API_KEY)
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 50)
    print("  [HASIL] LAPORAN")
    print("=" * 50)
    print(f"  Kepada        : {laporan.kepada}")
    print(f"  Nomor ST      : {laporan.nomor_st}")
    print(f"  Tanggal ST    : {laporan.tanggal_st}")
    print(f"  Hari/Tanggal  : {laporan.hari_tanggal}")
    print(f"  Tembusan      : {laporan.tembusan}")
    print(f"\n  Pelaksana ({len(laporan.pelaksana)} orang):")
    for i, p in enumerate(laporan.pelaksana, 1):
        print(f"    {i}. {p.nama} — {p.peran_tugas[:80]}")
    print(f"\n  Maksud/Tujuan : {laporan.maksud_tujuan[:80]}...")
    print(f"  Kegiatan      : {laporan.kegiatan_deskripsi[:80]}...")
    print(f"  Waktu         : {laporan.kegiatan_waktu_mulai} - {laporan.kegiatan_waktu_selesai}")
    print(f"  Tempat        : {laporan.kegiatan_tempat}")
    print(f"  Hasil ({len(laporan.hasil)} poin):")
    for h in laporan.hasil:
        print(f"    - {h[:80]}")
    print(f"  Penutup       : {laporan.penutup[:80]}...")
    print(f"  TTD           : {laporan.tempat_tanggal_ttd}")
    print(f"  Nama TTD      : {', '.join(laporan.nama_ttd)}")

    if args.render:
        output_dir = Path(__file__).parent.parent / "output"
        output_dir.mkdir(exist_ok=True)
        filename = f"laporan_agentic_{laporan.hari_tanggal.replace(' ', '_').replace(',', '')}.docx"
        output_path = output_dir / filename
        print(f"\n[DOCX] Merender ke {output_path}...")
        render_laporan(laporan, str(TEMPLATE_PATH), str(output_path))
        print(f"[OK] Laporan: {output_path}")

    print("\n[OK] Selesai.")


if __name__ == "__main__":
    main()
