# RISK — Pagar Risiko Hard-Coded (Non-Negotiable)

> Pagar ini di-enforce di lapisan **EA**, bukan di AI. Model/agent tidak memiliki
> kemampuan teknis untuk melewatinya. Perubahan file ini = major version bump +
> review manual.

## Batas Posisi
| Aturan | Nilai | Penegakan |
|--------|-------|-----------|
| Risiko per posisi | maks **1%** ekuitas | ukuran lot dihitung EA dari jarak SL |
| Posisi terbuka paralel | maks **2** | EA menolak sinyal baru |
| SL selalu ada | wajib | EA menolak order tanpa SL |

## Batas Harian / Global
| Aturan | Nilai | Penegakan |
|--------|-------|-----------|
| Loss harian | **3%** → EA berhenti sampai hari berikutnya | daily-loss guard |
| Drawdown ekuitas dari HWM | **10%** → sistem berhenti total + review manual | kill switch |
| Trading di sekitar news merah | dilarang ±15 menit | filter kalender ekonomi |

## Aturan Lain
- Tidak ada martingale, averaging-down, grid, atau lot multiplier.
- Tidak ada eksekusi pada simbol di luar daftar instrumen resmi.
- Setiap pelanggaran guard yang terdeteksi wajib terlog (bukti EA bekerja).

## Non-Goals (dilarang dibangun)
- Manajemen dana milik pihak lain (money manager / titip akun).
- Janji profit atau target return dalam materi publikasi apa pun.
