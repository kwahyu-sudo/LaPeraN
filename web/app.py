"""Flask web app for Laporan Perjalanan Dinas Generator."""
import os
import re
import sys
import tempfile
from pathlib import Path

import io

from flask import Flask, render_template, request, send_file, session, redirect, url_for, make_response

# Ensure core/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import GROQ_API_KEY, TEMPLATE_PATH
from core.pdf_extractor import extract_text_from_pdf, is_pdf_readable
# from core.ai_parser import parse_surat_tugas      # old (single-shot)
from agentic_parser import parse_surat_tugas          # new (agentic loop)
from core.renderer import render_laporan
from core.models import LaporanPerdin, Pelaksana


def _normalize_waktu(raw: str) -> str:
    """Strip descriptive time words (pagi, sore, WIB, dll), keep only HH:MM."""
    if not raw or raw.strip().lower() == "selesai":
        return raw
    m = re.search(r'(\d{1,2})[.:](\d{2})', raw)
    if m:
        return f"{m.group(1).zfill(2)}:{m.group(2)}"
    return raw

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB
UPLOAD_DIR = Path(tempfile.gettempdir()) / "perdin_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def _lap_to_dict(lap: LaporanPerdin) -> dict:
    return {
        "kepada": lap.kepada,
        "nomor_st": lap.nomor_st,
        "tanggal_st": lap.tanggal_st,
        "hari_tanggal": lap.hari_tanggal,
        "tembusan": lap.tembusan,
        "maksud_tujuan": lap.maksud_tujuan,
        "kegiatan_deskripsi": lap.kegiatan_deskripsi,
        "kegiatan_waktu_mulai": lap.kegiatan_waktu_mulai,
        "kegiatan_waktu_selesai": lap.kegiatan_waktu_selesai,
        "kegiatan_tempat": lap.kegiatan_tempat,
        "hasil_intro": lap.hasil_intro,
        "hasil": lap.hasil,
        "penutup": lap.penutup,
        "tempat_tanggal_ttd": lap.tempat_tanggal_ttd,
        "pelaksana": [{"nama": p.nama, "peran_tugas": p.peran_tugas} for p in lap.pelaksana],
        "nama_ttd": lap.nama_ttd,
    }


def _dict_to_lap(d: dict) -> LaporanPerdin:
    return LaporanPerdin(
        kepada=d.get("kepada", ""),
        nomor_st=d.get("nomor_st", ""),
        tanggal_st=d.get("tanggal_st", ""),
        hari_tanggal=d.get("hari_tanggal", ""),
        tembusan=d.get("tembusan", "Sekretaris Utama"),
        maksud_tujuan=d.get("maksud_tujuan", ""),
        kegiatan_deskripsi=d.get("kegiatan_deskripsi", ""),
        kegiatan_waktu_mulai=d.get("kegiatan_waktu_mulai", ""),
        kegiatan_waktu_selesai=d.get("kegiatan_waktu_selesai", "selesai"),
        kegiatan_tempat=d.get("kegiatan_tempat", ""),
        hasil_intro=d.get("hasil_intro", ""),
        hasil=d.get("hasil", []),
        penutup=d.get("penutup", ""),
        tempat_tanggal_ttd=d.get("tempat_tanggal_ttd", ""),
        pelaksana=[Pelaksana(**p) for p in d.get("pelaksana", [])],
        nama_ttd=d.get("nama_ttd", []),
    )


@app.route("/", methods=["GET"])
def index():
    error = request.args.get("error", "")
    return render_template("index.html", step="upload", error=error)


@app.route("/parse", methods=["POST"])
def parse():
    if "pdf" not in request.files:
        return redirect(url_for("index", error="Pilih file PDF dulu"))

    file = request.files["pdf"]
    if not file.filename.lower().endswith(".pdf"):
        return redirect(url_for("index", error="File harus PDF"))

    pdf_path = UPLOAD_DIR / file.filename
    file.save(pdf_path)

    if not is_pdf_readable(str(pdf_path)):
        pdf_path.unlink(missing_ok=True)
        return redirect(url_for("index", error="PDF tidak punya layer teks (scan). Upload TTE digital asli."))

    teks = extract_text_from_pdf(str(pdf_path))
    try:
        laporan = parse_surat_tugas(teks, GROQ_API_KEY)
    except Exception as e:
        pdf_path.unlink(missing_ok=True)
        return redirect(url_for("index", error=f"Gagal parse: {e}"))

    # Simpan data ke session + file path
    session["pdf_path"] = str(pdf_path)
    session["laporan"] = _lap_to_dict(laporan)
    session["filename"] = file.filename

    return render_template("index.html", step="confirm", laporan=_lap_to_dict(laporan))


@app.route("/render", methods=["POST"])
def render():
    data = session.get("laporan")
    pdf_path = session.get("pdf_path")
    if not data or not pdf_path:
        return redirect(url_for("index", error="Session expired, upload ulang"))

    # Merge edited fields from form
    for key in ("kepada", "nomor_st", "tanggal_st", "hari_tanggal", "tembusan",
                "maksud_tujuan", "kegiatan_deskripsi", "kegiatan_waktu_mulai", "kegiatan_waktu_selesai",
                "kegiatan_tempat",
                "hasil_intro", "penutup", "tempat_tanggal_ttd"):
        if key in request.form:
            val = request.form[key]
            if key in ("kegiatan_waktu_mulai", "kegiatan_waktu_selesai"):
                val = _normalize_waktu(val)
            data[key] = val

    # Pelaksana
    pelaksana = []
    i = 0
    while f"pelaksana_{i}_nama" in request.form:
        pelaksana.append(Pelaksana(
            nama=request.form[f"pelaksana_{i}_nama"],
            peran_tugas=request.form.get(f"pelaksana_{i}_peran", ""),
        ))
        i += 1
    if pelaksana:
        data["pelaksana"] = [{"nama": p.nama, "peran_tugas": p.peran_tugas} for p in pelaksana]

    # Hasil (dynamic list)
    hasil = []
    i = 0
    while f"hasil_{i}" in request.form:
        hasil.append(request.form[f"hasil_{i}"])
        i += 1
    if hasil:
        data["hasil"] = hasil

    # Nama TTD
    nama_ttd = []
    i = 0
    while f"ttd_{i}" in request.form:
        nama_ttd.append(request.form[f"ttd_{i}"])
        i += 1
    if nama_ttd:
        data["nama_ttd"] = nama_ttd

    laporan = _dict_to_lap(data)

    # Nama file: kegiatan + tanggal, di-sanitasi
    kegiatan = data.get("kegiatan_deskripsi", "laporan")[:40]
    tgl = data.get("hari_tanggal", "").split(",")[-1].strip()[:20]
    filename = f"laporan_{kegiatan}_{tgl}".replace(" ", "_")
    filename = "".join(c for c in filename if c.isalnum() or c in "_-") + ".docx"

    output_path = UPLOAD_DIR / filename
    render_laporan(laporan, str(TEMPLATE_PATH), str(output_path))

    session.clear()

    # Read the generated file into memory so send_file streams bytes
    # directly instead of relying on filesystem path (HF Spaces proxy
    # can corrupt path-based responses when MIME type is inferred).
    DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    file_bytes = output_path.read_bytes()
    file_size = len(file_bytes)
    buf = io.BytesIO(file_bytes)
    buf.seek(0)

    # Clean up temp file early (bytes already in memory)
    output_path.unlink(missing_ok=True)

    response = make_response(
        send_file(
            buf,
            mimetype=DOCX_MIME,
            as_attachment=True,
            download_name=filename,
        )
    )
    response.headers["Content-Length"] = file_size
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
