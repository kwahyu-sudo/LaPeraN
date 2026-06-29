"""Tool schemas + worker handlers untuk agentic parser.

Worker panggil model sesuai config.py — tiap tool bisa punya model sendiri.
"""

import json
import re
import groq

from config import GROQ_API_KEY
from core.models import LaporanPerdin, Pelaksana
from .config import MODEL_FOR_TOOL, REASONING_MODEL


def _normalize_waktu(raw: str) -> str:
    """Strip descriptive time words (pagi, sore, WIB, dll), keep only HH:MM."""
    if not raw or raw.strip().lower() == "selesai":
        return raw
    m = re.search(r'(\d{1,2})[.:](\d{2})', raw)
    if m:
        return f"{m.group(1).zfill(2)}:{m.group(2)}"
    return raw

# ── Tool schemas (dikirim ke reasoning LLM) ─────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "extract_header_fields",
            "description": (
                "Ekstrak field header surat tugas: kepada, nomor_st, "
                "tanggal_st, hari_tanggal pelaksanaan, dan tembusan. "
                "Teks PDF sudah tersedia, tidak perlu dikirim."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_pelaksana",
            "description": (
                "Ekstrak daftar pelaksana perjalanan dinas beserta peran/tugas "
                "masing-masing dari teks surat tugas. "
                "Teks PDF sudah tersedia, tidak perlu dikirim."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_laporan_content",
            "description": (
                "Generate narasi laporan perjalanan dinas. "
                "Parameter INPUT: kepada, pelaksana, hari_tanggal, nomor_st, tujuan_kegiatan. "
                "Output (maksud_tujuan, kegiatan, hasil, penutup, ttd) dihasilkan oleh worker model — "
                "jangan dikirim sebagai argumen."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kepada": {"type": "string"},
                    "pelaksana": {
                        "type": "array",
                        "description": "Daftar pelaksana dari hasil extract_pelaksana",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nama": {"type": "string"},
                                "peran_tugas": {"type": "string"}
                            },
                            "required": ["nama"]
                        }
                    },
                    "pelaksana_json": {
                        "type": "string",
                        "description": "DEPRECATED — gunakan pelaksana saja"
                    },
                    "hari_tanggal": {"type": "string"},
                    "nomor_st": {"type": "string"},
                    "tujuan_kegiatan": {
                        "type": "string",
                        "description": "Inferensikan dari konteks surat tugas"
                    }
                },
                "required": ["kepada", "hari_tanggal", "nomor_st", "tujuan_kegiatan"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_completeness",
            "description": (
                "Validasi apakah semua field LaporanPerdin sudah terisi. "
                "Return daftar field yang masih kosong atau perlu diperbaiki."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "laporan": {
                        "type": "object",
                        "description": "Objek LaporanPerdin saat ini dalam bentuk dict"
                    }
                },
                "required": ["laporan"]
            }
        }
    }
]


# ── Helpers ─────────────────────────────────────────────────────────

def _get_model(tool_name: str) -> str:
    """Ambil model untuk tool tertentu — fallback ke reasoning model."""
    return MODEL_FOR_TOOL.get(tool_name, REASONING_MODEL)


def _call_llm(system: str, user: str, api_key: str,
              model: str, temp: float = 0.0, max_tok: int = 500) -> dict:
    """Helper: call Groq, return parsed JSON."""
    client = groq.Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=temp,
        max_tokens=max_tok,
    )
    return json.loads(resp.choices[0].message.content)


# ── Worker implementations ──────────────────────────────────────────

def _extract_header(teks: str, api_key: str) -> dict:
    model = _get_model("extract_header_fields")
    return _call_llm(
        system=(
            "Ekstrak field header surat tugas perjalanan dinas. "
            "Return ONLY JSON dengan field:\n"
            "- kepada: jabatan penandatangan surat tugas (bukan pelaksana)\n"
            "- nomor_st: nomor surat tugas\n"
            "- tanggal_st: tanggal surat tugas\n"
            "- hari_tanggal: hari dan tanggal pelaksanaan\n"
            "- tembusan: pihak yang ditembus (default 'Sekretaris Utama' jika tidak ada)"
        ),
        user=f"Teks surat tugas:\n\n{teks[:4000]}",
        api_key=api_key,
        model=model,
        max_tok=500,
    )


def _extract_pelaksana(teks: str, api_key: str) -> list[dict]:
    model = _get_model("extract_pelaksana")
    data = _call_llm(
        system=(
            "Ekstrak daftar pelaksana perjalanan dinas. "
            "Return ONLY JSON. Format: {\"pelaksana\": [{\"nama\": \"...\", \"peran_tugas\": \"...\"}]}.\n\n"
            "PENTING — HANYA ekstrak pelaksana yang benar-benar ADA di teks surat tugas. "
            "JANGAN menambah atau menciptakan pelaksana baru.\n\n"
            "PERHATIAN PERAN_TUGAS: Dokumen surat tugas biasanya tidak mencantumkan peran "
            "masing-masing orang secara detail. Karena itu, peran_tugas harus DI-CIPTAKAN "
            "berdasarkan konteks kegiatan. Setiap orang WAJIB punya peran_tugas yang BERBEDA. "
            "Gunakan kalimat aktif (mis: 'Melaksanakan koordinasi pensertifikatan tanah bersama BPN'). "
            "BUKAN jabatan struktural dan BUKAN pangkat/golongan."
        ),
        user=f"Teks surat tugas:\n\n{teks[:4000]}",
        api_key=api_key,
        model=model,
        max_tok=600,
    )
    raw = data.get("pelaksana", data) if isinstance(data, dict) else data
    return raw if isinstance(raw, list) else [raw]


def _generate_content(args: dict, api_key: str, state: dict | None = None) -> dict:
    model = _get_model("generate_laporan_content")

    # ponytail: baca pelaksana dari state (hasil extract_pelaksana) dulu,
    # fallback ke args kalau model ngirim via parameter
    pelaksana = (state or {}).get("pelaksana", [])
    if not pelaksana:
        pelaksana = args.get("pelaksana", [])
    if not pelaksana:
        raw = args.get("pelaksana_json", "[]")
        try:
            pelaksana = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            pelaksana = []
    if isinstance(pelaksana, str):
        try:
            pelaksana = json.loads(pelaksana)
        except json.JSONDecodeError:
            pelaksana = []
    pelaksana_str = json.dumps(pelaksana, ensure_ascii=False, indent=2)

    return _call_llm(
        system=(
            "Kamu adalah penulis laporan perjalanan dinas pemerintah Indonesia. "
            "Buat narasi laporan berdasarkan data yang diberikan. "
            "Return ONLY JSON dengan field: maksud_tujuan, kegiatan_deskripsi, "
            "kegiatan_waktu_mulai (format jam, misal '08.00 WIB'), "
            "kegiatan_waktu_selesai (format jam, misal '12.00 WIB' atau 'selesai'), "
            "kegiatan_tempat (lokasi tujuan kegiatan, bukan alamat kantor pengirim), "
            "hasil_intro, hasil (list of strings — setiap item berupa kalimat deskriptif panjang 1-2 kalimat, bukan frasa pendek), penutup, "
            "tempat_tanggal_ttd (format 'Kota, DD MonthName YYYY', misal 'Bogor, 31 Agustus 2026' — BUKAN DD-MM-YYYY), "
            "nama_ttd (list of strings).\n\n"
            "PENTING — nama_ttd HARUS persis sama dengan nama-nama pelaksana yang diberikan. "
            "Jangan tambah atau kurangi. Urutannya juga sama.\n"
            "PENTING — kegiatan_waktu_mulai dan kegiatan_waktu_selesai adalah JAM, bukan tanggal. "
            "Gunakan format 'HH.MM WIB', jangan pakai format tanggal."
        ),
        user=(
            f"Kepada: {args.get('kepada', '')}\n"
            f"Pelaksana:\n{pelaksana_str}\n"
            f"Hari/Tanggal: {args.get('hari_tanggal', '')}\n"
            f"Nomor ST: {args.get('nomor_st', '')}\n"
            f"Tujuan Kegiatan: {args.get('tujuan_kegiatan', '')}"
        ),
        api_key=api_key,
        model=model,
        temp=0.3,
        max_tok=1000,
    )


def _validate(laporan: dict) -> list[str]:
    """Validasi lokal — tanpa LLM call (gratis).
    Returns field yang masih kosong. Hari/tanggal, nama_ttd dll
    tidak blocking — bisa diisi default nanti.
    """
    required = [
        "kepada", "nomor_st", "tanggal_st",
        "maksud_tujuan", "kegiatan_deskripsi", "kegiatan_tempat",
        "penutup", "tempat_tanggal_ttd",
    ]
    missing = []
    for field in required:
        val = laporan.get(field, "")
        if not val or (isinstance(val, str) and not val.strip()):
            missing.append(field)
    # soft fields — dicatat tapi tidak trigger retry loop
    for field in ("hari_tanggal", "pelaksana", "hasil", "nama_ttd"):
        val = laporan.get(field, [])
        if not val:
            missing.append(field)
    return missing


# ── Dispatcher ──────────────────────────────────────────────────────

def handle_tool_call(tool_name: str, tool_args: dict,
                     state: dict, api_key: str) -> str:
    """Dispatcher: panggil worker sesuai tool_name, update state, return JSON."""
    print(f"  [TOOL] Agent memanggil: {tool_name}")

    result: dict | list = {}

    if tool_name == "extract_header_fields":
        teks = state.get("_teks", "")
        result = _extract_header(teks, api_key)
        for k, v in result.items():
            if v:
                state[k] = v

    elif tool_name == "extract_pelaksana":
        teks = state.get("_teks", "")
        result = _extract_pelaksana(teks, api_key)
        if result:
            state["pelaksana"] = result

    elif tool_name == "generate_laporan_content":
        result = _generate_content(tool_args, api_key, state=state)
        for f in ("maksud_tujuan", "kegiatan_deskripsi",
                  "kegiatan_waktu_mulai", "kegiatan_waktu_selesai", "kegiatan_tempat",
                  "hasil_intro", "hasil", "penutup",
                  "tempat_tanggal_ttd", "nama_ttd"):
            if f in result:
                state[f] = result[f]
        # ponytail: normalize waktu (strip "pagi/sore/WIB" noise)
        if "kegiatan_waktu_mulai" in state:
            state["kegiatan_waktu_mulai"] = _normalize_waktu(state["kegiatan_waktu_mulai"])
        if "kegiatan_waktu_selesai" in state:
            state["kegiatan_waktu_selesai"] = _normalize_waktu(state["kegiatan_waktu_selesai"])
        # ponytail: nama_ttd harus match persis dari pelaksana (case-sensitive)
        pelaksana = state.get("pelaksana", [])
        if pelaksana:
            state["nama_ttd"] = [p["nama"] if isinstance(p, dict) else str(p)
                                 for p in pelaksana]

    elif tool_name == "validate_completeness":
        # ponytail: abaikan tool_args, validate state asli — reasoning model
        # sering ngirim data ngawur yang tidak match state real
        missing = _validate(state)
        if missing:
            print(f"  [WARN] Field belum lengkap: {', '.join(missing)}")
        else:
            print(f"  [OK] Semua field lengkap!")
        return json.dumps({
            "is_complete": len(missing) == 0,
            "missing_fields": missing,
        }, ensure_ascii=False)

    return json.dumps(result, ensure_ascii=False)


def state_to_laporan(state: dict) -> LaporanPerdin:
    """Convert accumulated state dict ke LaporanPerdin."""
    pelaksana_raw = state.get("pelaksana", [])
    if isinstance(pelaksana_raw, list):
        pelaksana = [
            Pelaksana(
                nama=p.get("nama", "") if isinstance(p, dict) else str(p),
                peran_tugas=p.get("peran_tugas", "") if isinstance(p, dict) else "",
            )
            for p in pelaksana_raw
        ]
    else:
        pelaksana = []

    hasil = state.get("hasil", [])
    if isinstance(hasil, str):
        hasil = [h.strip() for h in hasil.split("\n") if h.strip()]

    nama_ttd = state.get("nama_ttd", [])
    if isinstance(nama_ttd, str):
        nama_ttd = [n.strip() for n in nama_ttd.split("\n") if n.strip()]

    return LaporanPerdin(
        kepada=state.get("kepada", ""),
        pelaksana=pelaksana,
        tembusan=state.get("tembusan", "Sekretaris Utama"),
        hari_tanggal=state.get("hari_tanggal", ""),
        nomor_st=state.get("nomor_st", ""),
        tanggal_st=state.get("tanggal_st", ""),
        maksud_tujuan=state.get("maksud_tujuan", ""),
        kegiatan_deskripsi=state.get("kegiatan_deskripsi", ""),
        kegiatan_waktu_mulai=state.get("kegiatan_waktu_mulai", ""),
        kegiatan_waktu_selesai=state.get("kegiatan_waktu_selesai", "selesai"),
        kegiatan_tempat=state.get("kegiatan_tempat", ""),
        hasil_intro=state.get("hasil_intro", ""),
        hasil=hasil,
        penutup=state.get("penutup", ""),
        tempat_tanggal_ttd=state.get("tempat_tanggal_ttd", ""),
        nama_ttd=nama_ttd,
    )
