"""Reasoning loop — llama-3.1-8b-instant decide tool calls, worker tools dieksekusi terpisah.

Signature parse_surat_tugas(teks, api_key) -> LaporanPerdin
sama persis dengan core.ai_parser, jadi tinggal ganti import kalau mau switch.
"""

import json
import groq

from config import GROQ_API_KEY
from core.models import LaporanPerdin
from .config import REASONING_MODEL, MAX_ITERATIONS
from .tools import TOOLS, handle_tool_call, state_to_laporan, _validate

# Field yang bisa diisi default — tidak perlu retry loop
SOFT_FIELDS = {"hari_tanggal", "pelaksana", "hasil", "nama_ttd"}

SYSTEM_PROMPT = """
Kamu adalah agen AI yang bertugas membuat laporan perjalanan dinas dari surat tugas PDF.

KAMU PUNYA AKSES KE TOOLS. Gunakan tools secara berurutan:
1. extract_header_fields  → ambil field header surat tugas
2. extract_pelaksana      → ambil daftar pelaksana
3. generate_laporan_content → buat narasi laporan (panggil setelah header & pelaksana siap)
4. validate_completeness  → cek apakah semua field sudah lengkap

URUTAN WAJIB:
- Jangan panggil generate_laporan_content sebelum extract_header_fields dan extract_pelaksana.
- Setelah generate_laporan_content, panggil validate_completeness.
- Jika validate_completeness return missing_fields, panggil generate_laporan_content lagi
  dengan konteks lebih lengkap untuk mengisi field yang kurang.

Setiap tool call akan dieksekusi oleh model yang lebih akurat.
Kamu hanya perlu memutuskan tool mana yang dipanggil dan dengan argumen apa.
"""


def parse_surat_tugas(teks_pdf: str, api_key: str = "", konteks_hasil: str | None = None) -> LaporanPerdin:
    """Agentic version: reasoning loop + tool calls. Signature sama dengan original."""
    if not api_key:
        api_key = GROQ_API_KEY

    client = groq.Groq(api_key=api_key)
    state: dict = {"_teks": teks_pdf}
    if konteks_hasil:
        state["_konteks_hasil"] = konteks_hasil

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Buat laporan perjalanan dinas dari surat tugas berikut. "
            f"Teks PDF sudah tersimpan di state — kamu tidak perlu mengirimnya "
            f"saat memanggil tool extract_header_fields atau extract_pelaksana.\n\n"
            f"{teks_pdf[:2000]}"
        )},
    ]

    iterations = 0
    prev_missing: set = set()
    stall_count = 0

    print(f"\n{'='*50}")
    print(f"  [Agentic Loop] reasoning: {REASONING_MODEL}")
    print(f"{'='*50}\n")

    while iterations < MAX_ITERATIONS:
        iterations += 1
        print(f"\n--- Iterasi {iterations}/{MAX_ITERATIONS} ---")

        try:
            response = client.chat.completions.create(
                model=REASONING_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.0,
                max_tokens=500,  # ponytail: 1000 terlalu besar utk free tier
            )
        except groq.BadRequestError as e:
            # Groq returns 400 when reasoning model sends malformed tool args
            # (e.g. pelaksana as string instead of array). Inject error hint
            # so model can retry with corrected arguments.
            print(f"  [WARN] Groq 400 error: {e}")
            messages.append({
                "role": "user",
                "content": (
                    "Tool call sebelumnya GAGAL karena format argumen salah. "
                    "Jangan kirim pelaksana — data pelaksana sudah tersedia dari "
                    "extract_pelaksana. Cukup kirim kepada, hari_tanggal, nomor_st, "
                    "tujuan_kegiatan."
                ),
            })
            continue

        msg = response.choices[0].message

        if not msg.tool_calls:
            print("  [OK] Reasoning selesai - tidak ada tool calls.")
            break

        # Simpan pesan asisten + tool_calls
        assistant_msg = {"role": "assistant", "content": msg.content}
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                }
            }
            for tc in msg.tool_calls
        ]
        messages.append(assistant_msg)

        # Eksekusi tool calls
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            try:
                result_str = handle_tool_call(name, args, state, api_key)
            except Exception as exc:
                print(f"  [ERR] Tool {name} gagal: {exc}")
                result_str = json.dumps({"error": str(exc)}, ensure_ascii=False)

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_str,
            })

        # Cek progress: stop kalau cuma soft fields yg kurang
        now_missing = set(_validate(state))
        hard_missing = now_missing - SOFT_FIELDS
        if not hard_missing:
            print(f"  [OK] Hanya soft fields kurang - lanjut tanpa retry.")
            break

        # Stall detection: same set 2x berturut-turut
        if now_missing == prev_missing:
            stall_count += 1
            if stall_count >= 2:
                print(f"  [WARN] Field macet ({', '.join(sorted(now_missing))}) - force stop.")
                break
        else:
            stall_count = 0
        prev_missing = now_missing

    print(f"\n{'='*50}")
    print(f"  [OK] Agentic selesai - {iterations} iterasi")
    print(f"{'='*50}\n")

    # Fallback kalau state kosong
    if not state.get("kepada"):
        print("  [WARN] State kosong - fallback ke single-shot parser")
        return _fallback_single_shot(teks_pdf, api_key)

    laporan = state_to_laporan(state)

    missing = _validate(state)
    if missing:
        print(f"  [WARN] Field kosong: {', '.join(missing)}")
    else:
        print(f"  [OK] Semua field terisi")

    return laporan


def _fallback_single_shot(teks_pdf: str, api_key: str) -> LaporanPerdin:
    """Fallback ke single-shot parser asli kalau agentic loop gagal."""
    import importlib
    parser = importlib.import_module("core.ai_parser")
    return parser.parse_surat_tugas(teks_pdf, api_key)
