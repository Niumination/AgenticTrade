# S5-T3: Backtest v0.2 Robustness — OOS Split + Parameter Sensitivity

STATUS: BACKTEST / NOT VERIFIED. Semua angka di bawah adalah hasil simulasi
internal pada data tick Dukascopy XAUUSD 2020-2025, bukan track record nyata.
Jangan pernah menyajikan hasil ini sebagai performa riil (docs/VERIFICATION.md).

Script: `scripts/backtest_v02_robustness.py`
Hasil mentah: `backtest/results/bt3-robustness.json`, log append-only
`backtest/results/bt3-<year>-*.jsonl` (54 run: 6 tahun x 9 varian).
Engine tests: 26/26 OK (unittest, backtest/test_engine.py).

Baseline = v0.2 RR2.0 (regime filter EMA20/50 vs ATR14, news filter sintetis
NFP/CPI, slippage 1.0 pt base, komisi $7/lot round-turn). Semua varian RR 2.0
kecuali eksperimen OOS (grid RR).

## Eksperimen 1 — Out-of-sample split (grid RR sebagai "fit")

Strategi v0.2 rule-based tanpa koefisien yang di-fit; satu-satunya pilihan
parameter yang di-"optimasi" adalah RR dari grid {1.5, 2.0, 2.5}. Metode:
pilih RR terbaik di IS, terapkan tanpa perubahan di OOS.

Split A: IS 2020-2022, OOS 2023-2025
  Best RR di IS = 1.5  (IS total -5.57R; grid: 1.5=-5.57, 2.0=-13.85, 2.5=-21.07)
  OOS (RR 1.5): 2023 -10.18, 2024 -0.70, 2025 +10.96 -> OOS total +0.08R
  "Degradasi": +5.65R (OOS lebih baik, tapi keduanya ~flat; bukan sinyal edge)

Split B: IS 2023-2025, OOS 2020-2022
  Best RR di IS = 2.0  (IS total +20.88R; grid: 2.0=+20.88, 2.5=+11.60, 1.5=-5.49)
  OOS (RR 2.0): 2020 -0.16, 2021 -2.41, 2022 -11.28 -> OOS total -13.85R
  Degradasi: -34.73R (IS +20.88R -> OOS -13.85R; total positif sepenuhnya
  hilang di OOS)

Kesimpulan OOS: pilihan RR yang tampak optimal di satu periode tidak
berlanjut ke periode lain. Split B adalah red flag paling keras: seluruh
+20.88R "edge" berasal dari 2025 dan berbalik negatif di luar sampel.

## Eksperimen 2 — Sensitivitas EMA regime filter (geser +-5)

Signal diregenerasi penuh per varian; biaya tetap baseline. total_r:

| Tahun | EMA15/45 | EMA20/50 (base) | EMA25/55 |
|-------|----------|-----------------|----------|
| 2020  | +0.38    | -0.16           | +16.00   |
| 2021  | -2.38    | -2.41           | -2.39    |
| 2022  | -8.51    | -11.28          | -1.57    |
| 2023  | -6.56    | -4.39           | -6.90    |
| 2024  | -1.19    | -0.35           | +0.39    |
| 2025  | +19.26   | +25.63          | +17.12   |
| TOTAL | +1.01    | +7.03           | +22.65   |

Perhatikan: EMA25/55 (geser +5) memberi total 3.2x lipat baseline, terutama
via 2020 (+16.00R vs -0.16R) dan 2022 (-1.57R vs -11.28R). EMA15/45 (geser -5)
menghapus hampir seluruh keuntungan (+1.01R). Rentang antar varian: 21.64R.
Positif/negatif per tahun berubah dengan pergeseran kecil — hasil sangat
tidak stabil terhadap parameter filter regime.

## Eksperimen 3 — Sensitivitas slippage (geser +-50%)

Sinyal tetap (EMA20/50 RR2.0); hanya engine slippage berubah.

| Tahun | 0.5 pt | 1.0 pt (base) | 1.5 pt |
|-------|--------|---------------|--------|
| 2020  | +0.30  | -0.16         | -0.60  |
| 2021  | -2.22  | -2.41         | -2.60  |
| 2022  | -11.22 | -11.28        | -11.34 |
| 2023  | -4.19  | -4.39         | -4.60  |
| 2024  | -0.02  | -0.35         | -0.67  |
| 2025  | +26.40 | +25.63        | +24.87 |
| TOTAL | +9.04  | +7.03         | +5.06  |

Monoton dan proporsional dengan jumlah trade (2025 punya 139 trade) — tidak
mengubah tanda tahunan; rentang 3.98R. Relatif paling stabil.

## Eksperimen 4 — Sensitivitas komisi (geser +-50%)

Sinyal tetap; hanya komisi ($3.5 / $7.0 / $10.5 per lot round-turn).

| Tahun | $3.5  | $7.0 (base) | $10.5 |
|-------|-------|-------------|-------|
| 2020  | +0.17 | -0.16       | +0.54 |
| 2021  | -2.28 | -2.41       | -2.55 |
| 2022  | -11.11| -11.28      | -8.36 |
| 2023  | -4.21 | -4.39       | -4.58 |
| 2024  | -0.04 | -0.35       | -0.63 |
| 2025  | +26.12| +25.63      | +25.13|
| TOTAL | +8.65 | +7.03       | +9.56 |

Rentang 2.53R; efek kecil. (2020/2022 tidak monoton karena jumlah posisi
sedikit berubah — guard equity-DD/kill-switch terpicu beda.)

## Kesimpulan jujur (sesuai brief tugas)

**Parameter-sensitive, belum robust.**

- Slippage dan komisi: berpengaruh tapi tidak mengubah tanda total secara
  drastis (masih positif di semua varian, justru karena 2025).
- EMA regime filter: total bergeser dari +1.01R ke +22.65R hanya karena
  EMA 20/50 -> 15/45 vs 25/55 — pergeseran parameter kecil mengubah hasil
  secara besar dan tidak konsisten.
- OOS: split B (IS 2023-2025 -> OOS 2020-2022) menghapus seluruh keuntungan
  (-13.85R di OOS). Total v0.2 (+7.03R) bertahan hanya karena 2025
  (+25.63R); lima tahun lainnya net -18.6R. Ini pola klasik hasil yang
  digerakkan satu periode pasar, bukan edge yang stabil.
- Rekomendasi: jangan naikkan ukuran risiko berdasarkan hasil ini. Perbaikan
  berikutnya sebaiknya fokus pada stabilisasi filter regime (mis. walk-forward
  penuh, definizsi trend yang kurang parameter-dependent) sebelum iterasi
  parameter lebih lanjut.

Semua output tetap berlabel BACKTEST / NOT VERIFIED.
