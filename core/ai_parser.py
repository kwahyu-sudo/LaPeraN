import json
import groq

from .models import LaporanPerdin, Pelaksana

SYSTEM_PROMPT = """
Kamu adalah asisten administrasi pemerintah Indonesia yang membuat laporan perjalanan dinas.
Tugasmu adalah membaca teks surat tugas PDF, lalu mengembalikan data laporan dalam format JSON.

PENTING:
- Kembalikan HANYA JSON, tanpa preamble, tanpa markdown backtick
- Jika field tidak ditemukan, gunakan string kosong ""
- Gunakan bahasa formal birokrasi Indonesia untuk teks naratif
- Hari/tanggal format: "Kamis, 5 Maret 2026"
- Waktu format: "10.00 WIB - selesai"
"""

USER_PROMPT = """
Baca surat tugas berikut, lalu isi JSON untuk laporan perjalanan dinas.

PENTING untuk peran_tugas setiap pelaksana:
- Setiap pelaksana HARUS punya peran_tugas yang BERBEDA
- Tulis 1-2 kalimat deskriptif, bukan frase pendek
- Contoh: "Berkoordinasi dengan staf BPN Kota Tangerang Selatan terkait kelengkapan dokumen persyaratan ganti nama sertifikat." bukan "koordinasi dokumen"

{{
  "kepada": "Kepala Biro/Jabatan yang dituju laporan",
  "pelaksana": [
    {{"nama": "Nama Pelaksana 1", "peran_tugas": "Peran orang ini — BEDA dari yang lain"}},
    {{"nama": "Nama Pelaksana 2", "peran_tugas": "Peran orang ini — BEDA dari yang lain"}}
  ],
  "tembusan": "Sekretaris Utama; Pegawai yang Melaksanakan Perjalanan Dinas",
  "hari_tanggal": "Hari, Tanggal pelaksanaan",
  "nomor_st": "Nomor Surat Tugas",
  "tanggal_st": "Tanggal Surat Tugas",
  "maksud_tujuan": "Kalimat naratif maksud dan tujuan perjalanan dinas",
  "kegiatan_deskripsi": "Deskripsi kegiatan yang dilakukan",
  "kegiatan_waktu_mulai": "Waktu mulai, contoh: 08.00",
  "kegiatan_waktu_selesai": "Waktu selesai atau 'selesai'",
  "kegiatan_tempat": "Tempat pelaksanaan",
  "hasil_intro": "Kalimat intro hasil kegiatan",
  "hasil": ["Poin hasil kegiatan 1", "Poin hasil kegiatan 2", "Poin hasil kegiatan 3 (atau lebih jika ada)"],
  "penutup": "Kalimat penutup laporan",
  "tempat_tanggal_ttd": "Kota, Tanggal tanda tangan",
  "nama_ttd": ["Nama penandatangan 1", "Nama penandatangan 2"]
}}

Teks surat tugas:
{teks_pdf}
"""


def parse_surat_tugas(teks_pdf: str, api_key: str) -> LaporanPerdin:
    client = groq.Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.format(teks_pdf=teks_pdf)},
        ],
        temperature=0.0,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    data = json.loads(raw)

    return LaporanPerdin(
        kepada=data.get("kepada", ""),
        pelaksana=[Pelaksana(**p) for p in data.get("pelaksana", [])],
        tembusan=data.get("tembusan", ""),
        hari_tanggal=data.get("hari_tanggal", ""),
        nomor_st=data.get("nomor_st", ""),
        tanggal_st=data.get("tanggal_st", ""),
        maksud_tujuan=data.get("maksud_tujuan", ""),
        kegiatan_deskripsi=data.get("kegiatan_deskripsi", ""),
        kegiatan_waktu_mulai=data.get("kegiatan_waktu_mulai", ""),
        kegiatan_waktu_selesai=data.get("kegiatan_waktu_selesai", "selesai"),
        kegiatan_tempat=data.get("kegiatan_tempat", ""),
        hasil_intro=data.get("hasil_intro", ""),
        hasil=data.get("hasil", []),
        penutup=data.get("penutup", ""),
        tempat_tanggal_ttd=data.get("tempat_tanggal_ttd", ""),
        nama_ttd=data.get("nama_ttd", []),
    )
