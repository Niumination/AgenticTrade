# XAUUSD Tick Data (Dukascopy) — 2020–2025

Downloaded via `npx dukascopy-node -i xauusd -from <YYYY>-01-01 -to <YYYY+1>-01-01 -t tick -f csv` (UTC, per year).
CSV format: `timestamp (ms epoch, UTC), askPrice, bidPrice`. Flats excluded, no volume.

## Files (backtest/data/download/)

| Periode             | File                                  | Ukuran | Baris       |
|---------------------|---------------------------------------|--------|-------------|
| 2020-01-01–2021-01-01 | xauusd-tick-2020-01-01-2021-01-01.csv | 1.7 GB | 55,827,170 |
| 2021-01-01–2022-01-01 | xauusd-tick-2021-01-01-2022-01-01.csv | 1.6 GB | 53,099,638 |
| 2022-01-01–2023-01-01 | xauusd-tick-2022-01-01-2023-01-01.csv | 1.7 GB | 53,851,664 |
| 2023-01-01–2024-01-01 | xauusd-tick-2023-01-01-2024-01-01.csv | 1.1 GB | 36,428,829 |
| 2024-01-01–2025-01-01 | xauusd-tick-2024-01-01-2025-01-01.csv | 1.7 GB | 56,217,145 |
| 2025-01-01–2026-01-01 | xauusd-tick-2025-01-01-2026-01-01.csv | 2.2 GB | 71,403,972 |

Total: ~10 GB, 326,828,418 tick rows.

## Verifikasi (verify_data.py)

- Spread: 0 baris dengan ask-bid <= 0 di semua tahun. PASS.
- Gap data (>60s, di luar weekend Fri~21:00–Sun~23:00 UTC):
  - Mayoritas adalah break harian Dukascopy 21:59–23:00 UTC (~1 jam/hari) — normal & expected.
  - Sisa: lull intraday mikro (60–160s) pada pasar sepi — normal untuk tick data.
  - Satu gap 5 jam: 2022-01-17 (MLK holiday, Senin) — pasar US libur.
  - Tidak ada gap anomali yang perlu tindakan.
- Rentang: pertama/akhir tick tiap tahun sesuai sesi pasar (mulai ~23:00 UTC 1 Jan/hari pertama, akhir ~21:59 UTC hari kerja terakhir).

Catatan: 2025 file mencakup Jan–Des 2025 penuh (to 2026-01-01). 2020 gap pertama hari 1-2 Jan lebih banyak (likuiditas holiday rendah).

## Reproduksi

- `bash fetch_years.sh` (idempotent — skip file yang sudah ada)
- `python3 verify_data.py` (verifikasi baris/spread/gap)
