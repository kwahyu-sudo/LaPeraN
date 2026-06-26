from dataclasses import dataclass, field


@dataclass
class Pelaksana:
    nama: str
    peran_tugas: str = ""


@dataclass
class LaporanPerdin:
    """Data model yang match placeholder di template laporan real."""

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

    # Hasil Kegiatan
    hasil_intro: str = ""
    hasil: list[str] = field(default_factory=list)

    # Penutup
    penutup: str = ""

    # Tanda Tangan
    tempat_tanggal_ttd: str = ""
    nama_ttd: list[str] = field(default_factory=list)
