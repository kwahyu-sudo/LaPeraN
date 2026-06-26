"""Generator Laporan Perjalanan Dinas Otomatis.

Usage:
    python main.py <path_surat_tugas.pdf>
"""

import sys

from config import GROQ_API_KEY, TEMPLATE_PATH
from core.pdf_extractor import extract_text_from_pdf, is_pdf_readable
from core.ai_parser import parse_surat_tugas
from core.renderer import render_laporan
from core.models import LaporanPerdin


def _edit_manual(lap: LaporanPerdin) -> LaporanPerdin:
    print("\n--- Koreksi Manual ---")
    lap.kepada = input(f"Kepada [{lap.kepada}]: ") or lap.kepada
    lap.nomor_st = input(f"Nomor ST [{lap.nomor_st}]: ") or lap.nomor_st
    lap.tanggal_st = input(f"Tanggal ST [{lap.tanggal_st}]: ") or lap.tanggal_st
    lap.hari_tanggal = input(f"Hari, Tanggal [{lap.hari_tanggal}]: ") or lap.hari_tanggal
    lap.maksud_tujuan = input(f"Maksud & Tujuan [{lap.maksud_tujuan[:50]}...]: ") or lap.maksud_tujuan
    lap.kegiatan_deskripsi = input(f"Deskripsi Kegiatan [{lap.kegiatan_deskripsi[:50]}...]: ") or lap.kegiatan_deskripsi
    lap.kegiatan_waktu_mulai = input(f"Waktu Mulai [{lap.kegiatan_waktu_mulai}]: ") or lap.kegiatan_waktu_mulai
    lap.kegiatan_waktu_selesai = input(f"Waktu Selesai [{lap.kegiatan_waktu_selesai}]: ") or lap.kegiatan_waktu_selesai
    lap.kegiatan_tempat = input(f"Tempat [{lap.kegiatan_tempat}]: ") or lap.kegiatan_tempat
    lap.tempat_tanggal_ttd = input(f"Tempat, Tgl TTD [{lap.tempat_tanggal_ttd}]: ") or lap.tempat_tanggal_ttd

    for i, p in enumerate(lap.pelaksana, 1):
        print(f"\n  Pelaksana {i}:")
        p.nama = input(f"    Nama [{p.nama}]: ") or p.nama
        p.peran_tugas = input(f"    Peran [{p.peran_tugas[:40]}...]: ") or p.peran_tugas
    return lap


def _konfirmasi(lap: LaporanPerdin) -> LaporanPerdin:
    print("\n=== Hasil Ekstraksi Surat Tugas ===")
    print(f"  Kepada        : {lap.kepada}")
    print(f"  Nomor ST      : {lap.nomor_st}")
    print(f"  Tanggal ST    : {lap.tanggal_st}")
    print(f"  Hari/Tanggal  : {lap.hari_tanggal}")
    print(f"  Tembusan      : {lap.tembusan}")
    print(f"\n  Pelaksana ({len(lap.pelaksana)} orang):")
    for i, p in enumerate(lap.pelaksana, 1):
        print(f"    {i}. {p.nama} — {p.peran_tugas[:60]}")
    print(f"\n  Tempat        : {lap.kegiatan_tempat}")
    print(f"  Waktu         : {lap.kegiatan_waktu_mulai} - {lap.kegiatan_waktu_selesai}")

    if input("\nApakah data di atas sudah benar? (y/n): ").strip().lower() != "y":
        lap = _edit_manual(lap)
    return lap


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_surat_tugas.pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    print(f"Membaca PDF: {pdf_path}")
    if not is_pdf_readable(pdf_path):
        print("ERROR: PDF tidak memiliki layer teks. Kemungkinan hasil scan.")
        sys.exit(1)

    print("Mengekstrak teks dari PDF...")
    teks = extract_text_from_pdf(pdf_path)

    print("Menganalisis surat tugas dengan AI...")
    try:
        laporan = parse_surat_tugas(teks, GROQ_API_KEY)
    except Exception as e:
        print(f"ERROR: Gagal parse surat tugas: {e}")
        sys.exit(1)

    laporan = _konfirmasi(laporan)

    output_path = f"output/laporan_perdin_{laporan.hari_tanggal.replace(' ', '_').replace(',', '')}.docx"
    render_laporan(laporan, str(TEMPLATE_PATH), output_path)
    print(f"\nLaporan berhasil dibuat: {output_path}")


if __name__ == "__main__":
    main()
