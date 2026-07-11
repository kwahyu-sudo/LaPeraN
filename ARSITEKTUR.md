# Arsitektur: Generator Laporan Perjalanan Dinas Otomatis

> **Stack:** Python · Flask · pdfplumber · python-docx · Groq API (GPT-OSS-120B)  
> **Deploy:** Hugging Face Spaces (Docker)  
> **Input:** PDF Surat Tugas ber-TTE BSrE  
> **Output:** File `.docx` laporan perjalanan dinas

---

## 1. Alur Sistem

```
┌─────────────────────────────────────────────────────────────────────┐
│  User upload PDF via Web UI                                         │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  pdf_extractor.py: Extract teks mentah dari PDF                     │
│  ─ pdfplumber, x_tolerance=2, y_tolerance=2                        │
│  ─ Validasi PDF readable (bukan scan)                               │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ai_parser.py: LLM → JSON → LaporanPerdin object                    │
│  ─ Groq API (openai/gpt-oss-120b)                                  │
│  ─ Satu panggilan: parse + generate narasi sekaligus               │
│  ─ response_format={"type": "json_object"}                          │
│  ─ temperature=0.0 untuk konsistensi                                │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Web UI: Tampilkan hasil + konfirmasi user                          │
│  ─ Form edit semua field                                            │
│  ─ Tambah/hapus pelaksana, hasil kegiatan                           │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  renderer.py: Generate .docx dari template + data                   │
│  ─ Rebuild header (Kepada/Dari/Tembusan/Hari)                       │
│  ─ Rebuild tabel pelaksana (dynamic row count)                      │
│  ─ Rebuild hasil kegiatan (dynamic paragraph count)                 │
│  ─ Rebuild TTD (dynamic signature count)                            │
│  ─ Simpan via raw ZIP (bypass doc.save corruption)                  │
└─────────────────────────┬───────────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Download .docx                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Struktur Folder

```
perdin-generator/
├── Dockerfile                  # HF Spaces build
├── .dockerignore
├── requirements.txt            # pdfplumber, python-docx, groq, flask
├── README.md                   # HF Spaces frontmatter
├── config.py                   # GROQ_API_KEY, TEMPLATE_PATH
├── prepare_template.py         # Tambah placeholder ke template via raw XML
├── main.py                     # CLI entry point (alternatif)
│
├── core/
│   ├── __init__.py
│   ├── models.py               # Dataclass: LaporanPerdin, Pelaksana
│   ├── pdf_extractor.py        # Ekstrak teks PDF
│   ├── ai_parser.py            # LLM parse → LaporanPerdin
│   └── renderer.py             # Render .docx dari template
│
├── web/
│   ├── app.py                  # Flask app (upload → parse → render)
│   └── templates/
│       └── index.html          # Single-page UI
│
├── templates/
│   └── template_laporan.docx   # Template dengan {{PLACEHOLDER}}
│
├── input/                      # Upload PDF (temp)
└── output/                     # Generated .docx (temp)
```

---

## 3. Data Model

```python
# core/models.py

@dataclass
class Pelaksana:
    nama: str
    peran_tugas: str = ""

@dataclass
class LaporanPerdin:
    # Header
    kepada: str
    pelaksana: list[Pelaksana]
    tembusan: str = "Sekretaris Utama"
    hari_tanggal: str = ""

    # Dasar (Surat Tugas)
    nomor_st: str = ""
    tanggal_st: str = ""

    # Maksud dan Tujuan
    maksud_tujuan: str = ""

    # Kegiatan
    kegiatan_deskripsi: str = ""
    kegiatan_waktu_mulai: str = ""
    kegiatan_waktu_selesai: str = "selesai"
    kegiatan_tempat: str = ""

    # Hasil Kegiatan (dynamic list)
    hasil_intro: str = ""
    hasil: list[str] = field(default_factory=list)

    # Penutup
    penutup: str = ""

    # Tanda Tangan
    tempat_tanggal_ttd: str = ""
    nama_ttd: list[str] = field(default_factory=list)
```

---

## 4. Template Placeholder Mapping

| Placeholder | Sumber | Bagian |
|------------|--------|--------|
| `{{KEPADA}}` | LLM | Header |
| `{{NOMOR_ST}}` | LLM | Dasar |
| `{{TANGGAL_ST}}` | LLM | Dasar |
| `{{HARI_TANGGAL}}` | LLM | Header + Kegiatan |
| `{{TEMBUSAN}}` | Default/LM | Header |
| `{{MAKSUD_TUJUAN}}` | LLM | Maksud |
| `{{KEGIATAN_DESKRIPSI}}` | LLM | Kegiatan |
| `{{KEGIATAN_WAKTU}}` | LLM | Kegiatan |
| `{{KEGIATAN_TEMPAT}}` | LLM | Kegiatan |
| `{{HASIL_INTRO}}` | LLM | Hasil |
| `{{HASIL_1..5}}` | LLM | Hasil (dynamic) |
| `{{PENUTUP}}` | LLM | Penutup |
| `{{TEMPAT_TANGGAL_TTD}}` | LLM | TTD |
| `{{PELAKSANA_1..6}}` | LLM | TTD + Header |

---

## 5. Renderer Detail

`renderer.py` bekerja dalam 8 langkah:

1. **Format title** — center, left-indent 0, right-indent 0.01"
2. **Combine waktu** — `{mulai} WIB - {selesai}` atau `{mulai} WIB`  
3. **Replace `{{}}` placeholders** — via run text scan
4. **Rebuild Dari section** — P[3] `Kepada : ...`, P[4] `Dari : 1. ...\n2. ...`  
5. **Rebuild hasil** — clone/trim `{{HASIL_N}}` paragraphs
6. **Rebuild table** — clone/trim table rows, no bullets
7. **Rebuild TTD** — clone/trim signature paragraphs, normalize line spacing
8. **Raw XML save** — bypass `doc.save()` to avoid `<w:drawing>` corruption

### Raw XML Save

```python
# Instead of doc.save():
# 1. Get body XML from python-docx in-memory model
# 2. Strip any <w:drawing> elements
# 3. Wrap in <w:document> with proper namespaces
# 4. Write to ZIP with original template parts (minus images)
# 5. Strip image references from .rels and Content_Types.xml
```

---

## 6. LLM Prompt Design

**System prompt:** Asisten administrasi pemerintah Indonesia. Return ONLY JSON.

**User prompt template:**
```json
{
  "kepada": "...",
  "pelaksana": [
    {"nama": "...", "peran_tugas": "..."}
  ],
  "tembusan": "...",
  "hari_tanggal": "...",
  "nomor_st": "...",
  "tanggal_st": "...",
  "maksud_tujuan": "...",
  "kegiatan_deskripsi": "...",
  "kegiatan_waktu_mulai": "...",
  "kegiatan_waktu_selesai": "...",
  "kegiatan_tempat": "...",
  "hasil_intro": "...",
  "hasil": ["...", "...", "..."],
  "penutup": "...",
  "tempat_tanggal_ttd": "...",
  "nama_ttd": ["...", "..."]
}
```

**Key parameters:** `temperature=0.0`, `response_format={"type": "json_object"}`, `max_tokens=2000`

---

## 7. Web UI (index.html)

Single-page Flask template dengan 2 mode:

### Mode Upload
- Drag & drop zone untuk PDF
- Validasi format PDF
- Button "Parse dengan AI"

### Mode Konfirmasi
- Form edit: Informasi Umum, Pelaksana, Maksud & Kegiatan, Hasil Kegiatan, Penutup & TTD
- Tombol "+ Tambah Hasil" untuk dynamic list
- Submit via `fetch` → blob download
- Status button: Memproses → ✅ Unduhan Berhasil / ❌ Unduhan Gagal

---

## 8. Template Preparation

`prepare_template.py` memproses file `.docx` referensi menjadi template:

1. Baca raw XML dari ZIP
2. Replace exact text → `{{PLACEHOLDER}}`
3. Tulis ulang XML + copy semua file lain (kecuali `word/media/`)
4. Hapus **semua** gambar dan image references

Template referensi adalah file `.docx` yang sudah di-generate dengan format benar, lalu di-replace teks variabelnya dengan placeholder.

---

## 9. Dependencies

```
pdfplumber==0.11.4
python-docx==1.1.2
groq>=1.5.0
flask>=3.0.0
```

---

## 10. Deployment (Hugging Face Spaces)

### Dockerfile
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=7860
EXPOSE 7860
CMD python web/app.py
```

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ | API key dari Groq |

### Secrets di HF
Set `GROQ_API_KEY` di Settings → Repository Secrets.

---

## 11. Risiko & Limitasi

| Risiko | Dampak | Mitigasi |
|--------|--------|----------|
| Groq rate limit (100K TPD) | Proses gagal | Tunggu reset / upgrade tier |
| LLM salah ekstrak field | Data laporan salah | Langkah konfirmasi sebelum render |
| PDF scan (tanpa teks) | Ekstraksi gagal | Validasi `is_pdf_readable()` |
| Template docx corrupted | Word error | Raw XML save bypass |
| Nama pelaksana > 6 | Kelebihan slot | Dynamic clone/trim |

---

## 11. Perbaikan & Fitur Tambahan Terbaru
1. **Bug TTD pelaksana berkurang 1**: Memperbaiki pencocokan regex placeholder di `_rebuild_ttd` agar hanya memproses paragraf di area tanda tangan (`slots`), menghindari pencocokan `{{PELAKSANA_N}}` pada paragraf 4 (header "Dari") yang menyebabkan pergeseran indeks (off-by-one).
2. **Unduh File Terkunci**: Menambahkan mekanisme `setTimeout` di UI (`index.html`) untuk mengaktifkan kembali tombol unduh setelah 3 detik, mencegah tombol terkunci dalam status "Memproses...".

---

## 12. Pengembangan Lanjutan

- [ ] Model fallback (gemma2-9b / openai/gpt-oss-20b) jika rate limit
- [ ] Multiple template format
- [ ] Riwayat generate
- [ ] Export PDF
- [ ] Batch processing
- [ ] Drag-reorder pelaksana
