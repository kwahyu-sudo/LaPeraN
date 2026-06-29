# ARSITEKTUR LAPORAN PERDIN 2.0

> **Stack:** Python 3.12+ · Flask · pdfplumber · python-docx · Groq API  
> **Input:** PDF Surat Tugas ber-TTE BSrE  
> **Output:** File `.docx` laporan perjalanan dinas  
> **Last updated:** 29 Juni 2026

---

## 1. Alur Sistem (Dual Parser)

```
┌──────────────────────────────────────────────────────────────┐
│  User upload PDF via Web UI                                  │
└────────────────────────┬───────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  pdf_extractor.py: Ekstrak teks mentah PDF                   │
│  - pdfplumber (x_tolerance=2, y_tolerance=2)                 │
│  - is_pdf_readable() guard untuk PDF scan                    │
└────────────────────────┬───────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  AGENTIC PARSER (default)                                    │
│  agentic_parser/loop.py                                      │
│                                                              │
│  Reasoning: llama-3.1-8b-instant (decision making)           │
│  Workers (model per tool via agentic_parser/config.py):      │
│    extract_header_fields  → llama-3.3-70b-versatile          │
│    extract_pelaksana      → llama-3.3-70b-versatile          │
│    generate_laporan_content → llama-3.3-70b-versatile        │
│    validate_completeness  → pure Python (no LLM call)        │
│                                                              │
│  Fallback: core/ai_parser.py (single-shot) jika agentic gagal│
└────────────────────────┬───────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  Web UI: Form konfirmasi + edit semua field                  │
│  - Edit Kepada, Nomor ST, Tanggal, Tembusan                  │
│  - Edit Pelaksana (nama + peran)                             │
│  - Edit Maksud, Kegiatan, Waktu, Tempat                      │
│  - Edit Hasil Kegiatan (dynamic list, tambah item)           │
│  - Edit Penutup, Tempat/Tanggal TTD, Nama TTD                │
└────────────────────────┬───────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  renderer.py: Generate .docx dari template                   │
│  8-step pipeline (lihat §6)                                  │
└────────────────────────┬───────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────────┐
│  Download .docx                                              │
└──────────────────────────────────────────────────────────────┘
```

### CLI Path (Development)

```
python -m agentic_parser.cli <pdf>           # Agentic parse saja
python -m agentic_parser.cli <pdf> --render  # Parse + render .docx
```

---

## 2. Struktur Folder

```
perdin-generator/
├── Dockerfile
├── requirements.txt            # pdfplumber, python-docx, groq, flask, lxml
├── config.py                   # GROQ_API_KEY, TEMPLATE_PATH
├── main.py                     # CLI entry (single-shot parser)
├── prepare_template.py         # Raw XML template preparation
│
├── core/
│   ├── __init__.py
│   ├── models.py               # LaporanPerdin, Pelaksana
│   ├── pdf_extractor.py        # PDF → teks
│   ├── ai_parser.py            # Single-shot LLM parser (fallback)
│   └── renderer.py             # Template .docx renderer (8-step)
│
├── agentic_parser/
│   ├── __init__.py
│   ├── cli.py                  # CLI test harness
│   ├── config.py               # Model registry per tool
│   ├── loop.py                 # Reasoning loop (tool orchestration)
│   └── tools.py                # Tool schemas + worker implementations
│
├── web/
│   ├── app.py                  # Flask: upload → parse → render
│   └── templates/
│       └── index.html          # Single-page UI (upload + confirm)
│
├── templates/
│   ├── template_laporan.docx   # Template with {{PLACEHOLDER}}
│   ├── reference.docx          # Manual reference document
│   └── original.docx           # Original (pre-placeholder) document
│
├── input/                      # PDF upload (temp)
├── output/                     # Generated .docx
│
└── .github/
    └── copilot-instructions.md # Ponytail (lazy senior dev) rules
```

---

## 3. Data Model

```python
# core/models.py
from dataclasses import dataclass, field

@dataclass
class Pelaksana:
    nama: str
    peran_tugas: str = ""

@dataclass
class LaporanPerdin:
    # Header
    kepada: str                              # Jabatan penandatangan ST
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

    # Hasil Kegiatan
    hasil_intro: str = ""
    hasil: list[str] = field(default_factory=list)

    # Penutup
    penutup: str = ""

    # Tanda Tangan
    tempat_tanggal_ttd: str = ""
    nama_ttd: list[str] = field(default_factory=list)
```

---

## 4. Agentic Parser Architecture

### 4.1 Reasoning Loop (`loop.py`)

```
┌─────────────────────────────────────────┐
│  parse_surat_tugas(teks_pdf, api_key)   │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│  Reasoning Loop (max 5 iterations)      │
│  Model: llama-3.1-8b-instant            │
│  Tools: auto, temperature=0.0           │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ 1. extract_header_fields        │    │
│  │ 2. extract_pelaksana            │    │
│  │ 3. generate_laporan_content     │    │
│  │ 4. validate_completeness        │    │
│  └─────────────────────────────────┘    │
│                                         │
│  Stop conditions:                       │
│   - Only SOFT_FIELDS missing            │
│   - Same missing set 2x (stall detect)  │
│   - validate_completeness returns empty │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│  state_to_laporan(state)                │
│  → LaporanPerdin object                 │
│                                         │
│  Fallback: core.ai_parser (single-shot) │
│  jika state kosong                      │
└─────────────────────────────────────────┘
```

### 4.2 Tool Schemas (`tools.py`)

| Tool | Worker Model | Input | Output |
|---|---|---|---|
| `extract_header_fields` | llama-3.3-70b | (reads `_teks` from state) | `{kepada, nomor_st, tanggal_st, hari_tanggal, tembusan}` |
| `extract_pelaksana` | llama-3.3-70b | (reads `_teks` from state) | `[{nama, peran_tugas}, ...]` |
| `generate_laporan_content` | llama-3.3-70b | `{kepada, pelaksana, hari_tanggal, nomor_st, tujuan_kegiatan}` | `{maksud_tujuan, kegiatan_*, hasil, penutup, ttd}` |
| `validate_completeness` | (pure Python) | state dict | `{is_complete, missing_fields}` |

### 4.3 Key Design Decisions

- **State-based data passing**: `pelaksana` dibaca dari state (hasil `extract_pelaksana`), BUKAN dari args tool call. Reasoning model (3.1-8b) sering salah format saat meneruskan data kompleks.
- **Soft fields**: `hari_tanggal`, `pelaksana`, `hasil`, `nama_ttd` — tidak blocking jika kosong.
- **nama_ttd enforced**: Selalu di-overwrite dengan nama-nama dari `pelaksana` setelah `generate_laporan_content`.
- **Waktu normalization**: `_normalize_waktu()` di `tools.py` menormalisasi output LLM (`"pukul 08:00 WIB pagi"` → `"08:00"`) setelah `generate_laporan_content`, konsisten dengan `ai_parser.py`.
- **Stall detection**: Jika missing fields sama 2 iterasi berturut-turut → force stop.

---

## 5. Template Placeholder Mapping

| Placeholder | Lokasi Template | Sumber Data |
|---|---|---|
| `{{KEPADA}}` | P[3], P[8] | LLM: jabatan penandatangan ST |
| `{{NOMOR_ST}}` | P[8] | LLM |
| `{{TANGGAL_ST}}` | P[8] | LLM |
| `{{HARI_TANGGAL}}` | P[4], P[18] | LLM |
| `{{TEMBUSAN}}` | P[4] | LLM (default: "Sekretaris Utama") |
| `{{MAKSUD_TUJUAN}}` | P[11] | LLM |
| `{{KEGIATAN_DESKRIPSI}}` | P[17] | LLM |
| `{{KEGIATAN_WAKTU}}` | P[19] | Renderer: combine mulai+selesai + WIB |
| `{{KEGIATAN_TEMPAT}}` | P[20] | LLM: lokasi TUJUAN (bukan alamat kantor) |
| `{{HASIL_INTRO}}` | P[24] | LLM |
| `{{HASIL_1..5}}` | P[25-29] | LLM: kalimat deskriptif panjang |
| `{{PENUTUP}}` | P[32] | LLM |
| `{{TEMPAT_TANGGAL_TTD}}` | P[35] | LLM: format "Kota, DD MonthName YYYY" |
| `{{PELAKSANA_1..6}}` | P[4] (Dari), P[37-42] (TTD), Table | LLM + Renderer dynamic rebuild |

---

## 6. Renderer Pipeline (8 Steps)

### Step 0: Center Title
P[0] alignment=center, left_indent=0.

### Step 1: Normalize Waktu
`_normalize_waktu()`: ekstrak HH:MM dari raw string (misal "08.00 WIB" → "08:00").

### Step 2: Combine Waktu
```
mulai=08:00, selesai=12:00 → "08:00 WIB - 12:00 WIB"
mulai=08:00, selesai=selesai → "08:00 WIB"
```
Ponytail: WIB on both sides unless `selesai == "selesai"`.

### Step 3: Replace Simple Placeholders
`_replace_in_doc()`: scan all runs in all paragraphs + table cells, replace `{{KEY}}` with value.

### Step 4: Rebuild "Dari" Section
`_rebuild_dari_section()`: rebuild P[3] "Kepada : ..." and P[4] "Dari : 1. ... 2. ..." with dynamic pelaksana count. Adds bottom border on P[4].

### Step 5: Rebuild Hasil
`_rebuild_hasil()`: clone or trim `{{HASIL_N}}` paragraphs to match count. Clears ALL runs before setting value (ponytail: prevents template leftover text leaking).

### Step 6: Compress Spacing
Zero out spacing on empty paragraphs in TTD area (P[28]+).

### Step 7: Rebuild Table
`_rebuild_table()`: clone or trim table rows to match pelaksana count. Removes auto-numbering from table cells.

### Step 7b: Collapse Table→Kegiatan Gap
After table rebuild, collapse empty spacer paragraphs between table and "Kegiatan" heading. Table shrinks with fewer pelaksana but spacers stay fixed → collapse them. Set minimal 6pt/2pt spacing on Kegiatan heading and description.

### Step 7c: Rebuild TTD
`_rebuild_ttd()`: 
- Find first `{{PELAKSANA_N}}` slot dynamically (skip P[4] inline Dari section)
- Clone or trim signature paragraphs
- Strip `w:numPr` from unused slots to prevent ghost "3." "4." numbering
- Enforce `nama_ttd` = pelaksana names

### Step 8: Raw XML Save
Bypass `doc.save()`:
1. Get body XML, strip `<w:drawing>` elements
2. Extract namespace declarations from template's `word/document.xml`
3. Wrap in `<w:document>` with original namespaces
4. Write to ZIP: custom `word/document.xml` + all original parts (minus `word/media/`)
5. Strip image references from `.rels` and `[Content_Types].xml`

---

## 7. LLM Prompt Requirements (Diverged from 1.0)

| Field | Requirement |
|---|---|
| `kepada` | Jabatan **penandatangan surat tugas** (bukan "orang yang dituju", bukan pelaksana) |
| `kegiatan_tempat` | **Lokasi tujuan** kegiatan (bukan alamat kantor pengirim) |
| `hasil[]` | Kalimat deskriptif **panjang** (1-2 kalimat), bukan frasa pendek |
| `tempat_tanggal_ttd` | Format **"Kota, DD MonthName YYYY"** (misal "Bogor, 31 Agustus 2026") — BUKAN "DD-MM-YYYY" |
| `kegiatan_waktu_mulai` | Format **"HH.MM WIB"** (jam, bukan tanggal) |
| `kegiatan_waktu_selesai` | Format **"HH.MM WIB"** atau **"selesai"** |
| `nama_ttd` | **Persis sama** dengan nama pelaksana, urutan sama |
| `pelaksana` | HANYA yang ada di ST, jangan menambah |

---

## 8. Known Fixes & Defects

Lihat `/memories/repo/template-defects.md` dan `/memories/repo/requirements-laporan.md`

### Major fixes (Juni 2026):

1. **Prompt kepaada**: "orang yang dituju" → "penandatangan surat tugas"
2. **WIB pada selesai**: renderer cuma tambah WIB di mulai → sekarang kedua sisi
3. **Tempat = tujuan**: prompt "tempat kegiatan" → "lokasi tujuan kegiatan"
4. **Hasil pendek**: prompt "poin hasil" → "kalimat deskriptif panjang 1-2 kalimat"
5. **Tool call 400**: `pelaksana_json` string → `pelaksana` array type
6. **Stray comma bug**: koma nakal di `tools.py:210` mengubah string jadi tuple → Groq API reject
7. **TTD ghost numbering**: `pi >= 36` hardcoded → dynamic slot detection + strip `w:numPr`
8. **Tanggal numerik**: prompt "DD-MM-YYYY" → "DD MonthName YYYY"
9. **Gap tabel→Kegiatan**: spacer collapse + tight spacing setelah table rebuild
10. **Prompt inconsistency agentic vs single-shot**: 5 gap ditemukan dan diselaraskan:
    - `kepada`: `ai_parser.py` tidak ada klarifikasi "(bukan pelaksana)" → ditambahkan
    - `tembusan`: `ai_parser.py` tidak memberi tahu LLM default "Sekretaris Utama" → ditambahkan di prompt
    - `kegiatan_waktu_mulai/selesai`: `ai_parser.py` zero format guidance → ditambah "HH.MM WIB, JAM bukan tanggal"
    - `nama_ttd`: `ai_parser.py` hanya "jumlah sama" → diperketat "persis sama nama & urutan"
    - `peran_tugas`: `tools.py` tidak ada larangan "BUKAN jabatan struktural/pangkat" → ditambahkan
11. **`_normalize_waktu` missing di agentic**: fungsi normalisasi hanya ada di `ai_parser.py` → ditambahkan ke `tools.py` + dipanggil setelah `generate_laporan_content`

---

## 9. Dependencies

```txt
pdfplumber>=0.11.0
python-docx>=1.1.0
groq>=1.5.0
flask>=3.0.0
lxml>=5.0.0
```

---

## 10. Deployment

### Web App
```bash
cd perdin-generator
set PYTHONIOENCODING=utf-8
python web/app.py
# → http://127.0.0.1:5000
```

### CLI Test
```bash
python -m agentic_parser.cli input/contoh_ST_signed.pdf --render
```

### Docker
```bash
docker build -t perdin-generator .
docker run -p 7860:7860 -e GROQ_API_KEY=$GROQ_API_KEY perdin-generator
```
