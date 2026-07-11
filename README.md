---
title: Generator Laporan Perjalanan Dinas
emoji: 📄
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# LaPeraN — Agentic Document Generator for Civil Servant Administration

> **Upload PDF Surat Tugas → AI parse → Konfirmasi → Download .docx**

[![Live Demo](https://img.shields.io/badge/🤗%20Live%20Demo-HuggingFace%20Spaces-blue)](https://huggingface.co/spaces/kwahyu/LaPeraN)
[![Kaggle](https://img.shields.io/badge/Kaggle-Submission-20BEFF)](https://www.kaggle.com/competitions/vibecoding-agents-capstone-project)

---

## What is LaPeraN?

LaPeraN (**Laporan Perjalanan Dinas Generator**) is an AI agent that automates the creation of official government travel reports for Indonesian civil servants (ASN/PNS).

Every business trip requires a formal *Laporan Perjalanan Dinas* — a structured document that must be written in formal bureaucratic Indonesian, follow strict institutional formatting, and be submitted after each trip. Doing this manually takes approximately **60 minutes per report**. LaPeraN reduces this to an estimated **10 minutes**, most of which is the officer reviewing AI-generated content before downloading.

**Target users:** 5.2 million Indonesian civil servants (BKN, Semester I 2025), 77% of whom are in regional institutions outside Jakarta where access to modern administrative tools is limited.

---

## How It Works

```
[PDF Surat Tugas TTE BSrE]
        ↓
[pdfplumber: extract text layer]
        ↓
[Agentic Parser — reasoning loop]
  openai/gpt-oss-20b (orchestrator)
    ├─→ extract_header_fields   → openai/gpt-oss-120b
    ├─→ extract_pelaksana       → openai/gpt-oss-120b
    ├─→ generate_laporan_content → openai/gpt-oss-120b
    └─→ validate_completeness   → pure Python
        ↓ loop until complete
[Human confirmation form]
        ↓
[renderer.py: fill institutional .docx template]
        ↓
[Download ready-to-sign .docx]
```

The agent uses **tool-use with autonomous decision-making** — the orchestrator model decides which tools to call and in what order, iterating until all required fields are validated. If the agentic loop fails, a single-shot fallback parser (`core/ai_parser.py`) ensures the user always gets a result.

---

## Cara Pakai

1. Upload PDF Surat Tugas (format TTE BSrE)
2. AI otomatis ekstrak data dan generate narasi laporan
3. Koreksi jika ada yang salah
4. Klik Generate & Download

---

## Running Locally

### Prerequisites
- Python 3.12+
- [Groq API key](https://console.groq.com) (free tier works)
- Your institution's travel report `.docx` template

### Setup

```bash
git clone https://github.com/kwahyu-sudo/LaPeraN.git
cd LaPeraN
pip install -r requirements.txt
```

### Template Setup

LaPeraN requires a `.docx` template file at `templates/template_laporan.docx`.

The template is **not included in this repo** — it contains an institution-specific document format. To use LaPeraN with your own template:

1. Take your institution's travel report `.docx`
2. Replace all variable fields with `{{PLACEHOLDER}}` tags according to this mapping:

| Placeholder | Field |
|---|---|
| `{{KEPADA}}` | Jabatan penandatangan surat tugas |
| `{{NOMOR_ST}}` | Nomor surat tugas |
| `{{TANGGAL_ST}}` | Tanggal surat tugas |
| `{{HARI_TANGGAL}}` | Hari dan tanggal pelaksanaan |
| `{{TEMBUSAN}}` | Tembusan |
| `{{MAKSUD_TUJUAN}}` | Maksud dan tujuan |
| `{{KEGIATAN_DESKRIPSI}}` | Deskripsi kegiatan |
| `{{KEGIATAN_WAKTU}}` | Waktu pelaksanaan |
| `{{KEGIATAN_TEMPAT}}` | Lokasi tujuan |
| `{{HASIL_INTRO}}` | Kalimat pembuka hasil kegiatan |
| `{{HASIL_1}}` ... `{{HASIL_5}}` | Hasil kegiatan (per item) |
| `{{PENUTUP}}` | Paragraf penutup |
| `{{TEMPAT_TANGGAL_TTD}}` | Tempat dan tanggal tanda tangan |
| `{{PELAKSANA_1}}` ... `{{PELAKSANA_6}}` | Nama pelaksana (TTD + tabel) |

3. Save as `templates/template_laporan.docx`

See `ARSITEKTUR_LAPORAN_PERDIN_2_0.md` for full placeholder mapping with paragraph indices.

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | ✅ | API key dari [Groq Console](https://console.groq.com) |

```bash
# Windows
set GROQ_API_KEY=your_key_here
set PYTHONIOENCODING=utf-8
python web/app.py

# Linux/Mac
export GROQ_API_KEY=your_key_here
python web/app.py
```

App runs at `http://127.0.0.1:5000`

### CLI (Development / Testing)

```bash
# Parse only
python -m agentic_parser.cli input/your_surat_tugas.pdf

# Parse + render .docx
python -m agentic_parser.cli input/your_surat_tugas.pdf --render
```

### Docker

```bash
docker build -t laporan-perdin .
docker run -p 7860:7860 -e GROQ_API_KEY=$GROQ_API_KEY laporan-perdin
```

---

## Project Structure

```
LaPeraN/
├── agentic_parser/
│   ├── loop.py        # Reasoning loop (tool orchestration)
│   ├── tools.py       # Tool schemas + worker implementations
│   ├── config.py      # Model registry per tool
│   └── cli.py         # CLI test harness
├── core/
│   ├── models.py      # LaporanPerdin, Pelaksana dataclasses
│   ├── pdf_extractor.py  # PDF text extraction (pdfplumber)
│   ├── ai_parser.py   # Single-shot fallback parser
│   └── renderer.py    # 8-step .docx template renderer
├── web/
│   ├── app.py         # Flask app
│   └── templates/
│       └── index.html # Upload + confirmation UI
├── templates/         # .docx templates (not in repo — see above)
├── Dockerfile
└── requirements.txt
```

---

## Dependencies

```
pdfplumber>=0.11.0
python-docx>=1.1.0
groq>=1.5.0
flask>=3.0.0
lxml>=5.0.0
```

---

## Analytics — Vercel Speed Insights & Web Analytics

LaPeraN is a **Flask** app (not Next.js), so the framework-specific `<SpeedInsights/>` and
`<Analytics/>` components do not apply. Instead, the framework-agnostic Vercel snippets are
injected directly into the Jinja2 template at `web/templates/index.html`, just before `</body>`:

```html
<!-- Speed Insights -->
<script>
  window.si = function a(...params) { (window.siq = window.siq || []).push(params); };
</script>
<script defer src="/_vercel/speed-insights/script.js"></script>

<!-- Web Analytics -->
<script defer src="/_vercel/insights/script.js"></script>
```

Notes:
- The scripts are served automatically from `/_vercel/...` when deployed on Vercel.
- They are a no-op in local/dev environments (Vercel only serves the scripts in production builds).
- `@vercel/speed-insights` and `@vercel/analytics` are listed in the repo root `package.json` solely
  for this purpose; no Node build step is required.
- Data flows into the Speed Insights and Analytics dashboards on Vercel.

---

## Agentic Concepts Demonstrated

| Concept | Implementation |
|---|---|
| Tool use | 4 tools with explicit JSON schemas |
| Autonomous decision-making | Orchestrator decides tool sequence without hardcoded order |
| Self-validation loop | `validate_completeness` triggers retry on missing fields |
| Dual-model routing | Lightweight model for orchestration, larger model for execution |
| Stall detection | Force-stops if missing fields unchanged across 2 iterations |
| Graceful fallback | Single-shot parser if agentic loop fails |
| Human-in-the-loop | Confirmation form before document generation |

---

## Known Limitations

- Rate-limited by Groq free tier (100K tokens/day)
- Template is institution-specific — not bundled with repo
- Scanned PDFs (non-TTE) not supported (no OCR)
- Single template format only

---

## License

MIT
