"""Replace text with placeholders in raw docx XML to preserve drawings/images."""
import re
from zipfile import ZipFile
from shutil import copyfile
from pathlib import Path
import tempfile

SRC = r"e:\Personal\Research_Project\LaperJadin_Generator\perdin-generator\templates\template_laporan.docx"

# Read XML from docx
with ZipFile(SRC) as z:
    doc_xml = z.read('word/document.xml').decode('utf-8')

pairs = [
    ("Kepala Biro Manajemen Barang Milik Negara dan Pengadaan", "{{KEPADA}}"),
    ("B-1988/II.2.4/PL.02.04/6/2026", "{{NOMOR_ST}}"),
    ("24 Juni 2026", "{{TANGGAL_ST}}"),
    ("Kamis, 25 Juni 2026", "{{HARI_TANGGAL}}"),
    ("Darmawati Anggraini", "{{PELAKSANA_1}}"),
    ("Syaiful Ramadhan", "{{PELAKSANA_2}}"),
    ("Fitrisia Aminah Putri", "{{PELAKSANA_3}}"),
    ("Kurniawan Wahyu I", "{{PELAKSANA_4}}"),
    ("{{PELAKSANA_4}}llahi", "{{PELAKSANA_4}}"),
    ("Berlin Fernandes", "{{PELAKSANA_5}}"),
    ("Ronaldo Treagan", "{{PELAKSANA_6}}"),
    ("Melaksanakan rapat koordinasi penyelesaian permasalahan pertanahan dan persertipikatan tanah milik BRIN di Wilayah Kabupaten Bogor", "{{MAKSUD_TUJUAN}}"),
    ("Rapat koordinasi penyelesaian permasalahan pertanahan dan persertipikatan tanah milik BRIN di Wilayah Kabupaten Bogor", "{{KEGIATAN_DESKRIPSI}}"),
    ("09.00 WIB", "{{KEGIATAN_WAKTU}}"),
    ("KST Soekarno, Cibinong, Kabupaten Bogor, Provinsi Jawa Barat", "{{KEGIATAN_TEMPAT}}"),
    (" memiliki selisih hasil pengukuran", ""),
    ("Hasil kegiatan rapat koordinasi penyelesaian permasalahan pertanahan dan persertipikatan tanah milik BRIN di Wilayah Kabupaten Bogor", "{{HASIL_INTRO}}"),
    (" adalah sebagai berikut", ""),
    ("Perbedaan sistem pengukuran tanah", "{{HASIL_1}}"),
    (" zaman dahulu dengan sekarang memungkinkan adanya selisih hasil pengukuran", ""),
    ("Penyelesaian proses pensertipikatan SHP 1 Cibinong", "{{HASIL_2}}"),
    ("ahaman karena selisih luasan.", ""),
    ("SHP 1 Pabuaran dan SHP 1 ", "{{HASIL_3}}"),
    ("BRIN perlu menyiapkan patok untuk mempermudah proses pengukuran tanah.", "{{HASIL_4}}"),
    ("Selanjutnya akan diagendakan kembali rapat dengan BPN Kab. Bogor.", "{{HASIL_5}}"),
    ("Dengan demikian, kegiatan rapat koordinasi penyelesaian permasalahan pertanahan dan persertipikatan tanah milik BRIN di Wilayah Kabupaten Bogor telah selesai dilaksanakan dengan baik dan sesuai dengan", "{{PENUTUP}}"),
    (" tujuan yang diharapkan", ""),
    ("Jakarta, 26 Juni 2026", "{{TEMPAT_TANGGAL_TTD}}"),
    (", yang selanjutnya pengukuran dan penataan batas dapat dilakukan", ""),
]

for old, new in pairs:
    n = doc_xml.count(old)
    if n:
        doc_xml = doc_xml.replace(old, new)
        print(f"  {n}x '{old[:50]}' -> '{new[:50]}'")

# Write back preserving all other files
tmp = Path(tempfile.mktemp(suffix='.docx'))
with ZipFile(tmp, 'w') as zout:
    zout.writestr('word/document.xml', doc_xml.encode('utf-8'))
    with ZipFile(SRC) as zin:
        for name in zin.namelist():
            if name == 'word/document.xml':
                continue
            zout.writestr(name, zin.read(name))

copyfile(tmp, SRC)
tmp.unlink()
print(f"\nDone.")
