"""Single-shot parser: one LLM call, returns structured JSON -> LaporanPerdin."""

import json

import groq

from config import GROQ_API_KEY
from .models import LaporanPerdin, Pelaksana
from .utils import normalize_waktu, sanitize_konteks

SYSTEM_PROMPT = """
Kamu adalah asisten administrasi pemerintah Indonesia.
Ekstrak informasi dari surat tugas berikut dan ubah menjadi laporan perjalanan dinas.

Return ONLY JSON dengan struktur berikut:
{
    "kepada": "nama jabatan penandatangan surat tugas (bukan pelaksana)",
    "pelaksana": [{"nama": "...", "peran_tugas": "..."}],
    "tembusan": "pihak yang ditembus (default 'Sekretaris Utama' jika tidak ditemukan)",
    "hari_tanggal": "hari, tanggal pelaksanaan",
    "nomor_st": "nomor surat tugas",
    "tanggal_st": "tanggal surat tugas",
    "maksud_tujuan": "maksud dan tujuan perjalanan dinas",
    "kegiatan_deskripsi": "deskripsi kegiatan yang dilaksanakan",
    "kegiatan_waktu_mulai": "waktu mulai kegiatan (format jam, misal '08.00 WIB' — JAM, bukan tanggal)",
    "kegiatan_waktu_selesai": "waktu selesai kegiatan (format jam, misal '12.00 WIB' atau 'selesai' — JAM, bukan tanggal)",
    "kegiatan_tempat": "tempat/lokasi tujuan kegiatan (bukan alamat kantor pengirim)",
    "hasil_intro": "kalimat pembuka hasil kegiatan",
    "hasil": ["hasil 1: kalimat deskriptif panjang (1-2 kalimat, bukan frasa pendek)", "hasil 2: ..."],
    "penutup": "kalimat penutup laporan",
    "tempat_tanggal_ttd": "tempat, tanggal tanda tangan (format: 'Kota, DD MonthName YYYY', misal 'Bogor, 31 Agustus 2026' — BUKAN format DD-MM-YYYY)",
    "nama_ttd": ["nama penanda tangan 1", "nama penanda tangan 2", ...]
}

Isi semua field berdasarkan teks surat tugas. Jika ada field yang tidak ditemukan,
isi dengan string kosong atau array kosong.

PERHATIAN PERAN_TUGAS (sangat penting):
- "peran_tugas" TIDAK bisa diekstrak langsung dari dokumen. Dokumen surat tugas biasanya
  tidak mencantumkan peran masing-masing orang secara detail.
- Karena itu, peran_tugas harus DI-GENERATE / DI-CIPTAKAN oleh kamu berdasarkan konteks
  kegiatan perjalanan dinas. Gunakan imajinasimu untuk membuat uraian tugas yang realistis
  dan spesifik untuk SETIAP orang.
- Setiap pelaksana WAJIB memiliki peran_tugas yang BERBEDA satu sama lain.
- Format: kalimat aktif yang menjelaskan kontribusi spesifik orang tersebut
  (mis: "Melaksanakan koordinasi pensertifikatan tanah bersama BPN",
   "Menyusun laporan hasil koordinasi", "Mendampingi tim dalam verifikasi lapangan").
- BUKAN jabatan struktural dan BUKAN pangkat/golongan.

PENTING — JUMLAH PELAKSANA:
- HANYA ekstrak pelaksana yang benar-benar ADA di dalam teks surat tugas.
- JANGAN menambah atau menciptakan pelaksana baru yang tidak disebutkan.
- Jumlah pelaksana di nama_ttd HARUS SAMA dengan jumlah pelaksana.
- nama_ttd HARUS persis sama (nama dan urutan) dengan nama-nama di pelaksana.
- Jika dokumen hanya menyebutkan 2 orang, maka pelaksana hanya 2 orang.
"""


def parse_surat_tugas(teks_pdf: str, api_key: str = "", konteks_hasil: str | None = None) -> LaporanPerdin:
    if not api_key:
        api_key = GROQ_API_KEY

    client = groq.Groq(api_key=api_key)

    konteks_hasil = sanitize_konteks(konteks_hasil)

    user_content = f"Proses surat tugas berikut:\n\n{teks_pdf}"
    if konteks_hasil:
        user_content += (
            f"\n\nKONTEKS HASIL PERJALANAN DARI USER:\n{konteks_hasil}\n"
            "Gunakan konteks tersebut sebagai DASAR untuk membuat bagian 'hasil' (hasil_intro & list hasil). "
            "Kembangkan menjadi kalimat paragraf yang lebih detail dan formal."
        )

    resp = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=2000,
    )

    data = json.loads(resp.choices[0].message.content)

    pelaksana_raw = data.get("pelaksana", [])
    if isinstance(pelaksana_raw, dict):
        pelaksana_raw = pelaksana_raw.get("pelaksana", [])

    pelaksana = [
        Pelaksana(nama=p.get("nama", ""), peran_tugas=p.get("peran_tugas", ""))
        for p in (pelaksana_raw if isinstance(pelaksana_raw, list) else [])
    ]

    return LaporanPerdin(
        kepada=data.get("kepada", ""),
        pelaksana=pelaksana,
        tembusan=data.get("tembusan", "Sekretaris Utama"),
        hari_tanggal=data.get("hari_tanggal", ""),
        nomor_st=data.get("nomor_st", ""),
        tanggal_st=data.get("tanggal_st", ""),
        maksud_tujuan=data.get("maksud_tujuan", ""),
        kegiatan_deskripsi=data.get("kegiatan_deskripsi", ""),
        kegiatan_waktu_mulai=normalize_waktu(data.get("kegiatan_waktu_mulai", "")),
        kegiatan_waktu_selesai=normalize_waktu(data.get("kegiatan_waktu_selesai", "selesai")),
        kegiatan_tempat=data.get("kegiatan_tempat", ""),
        hasil_intro=data.get("hasil_intro", ""),
        hasil=data.get("hasil", []),
        penutup=data.get("penutup", ""),
        tempat_tanggal_ttd=data.get("tempat_tanggal_ttd", ""),
        nama_ttd=data.get("nama_ttd", []),
    )
