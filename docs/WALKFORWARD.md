# S6-T2: Walk-Forward Optimization — Strategi v0.3

STATUS: BACKTEST / NOT VERIFIED. Semua angka di bawah adalah hasil simulasi
internal pada data tick Dukascopy XAUUSD 2020-2025, bukan track record nyata.
Jangan pernah menyajikan hasil ini sebagai performa riil (docs/VERIFICATION.md).

Script: `scripts/walkforward.py` (tabel: `scripts/walkforward_tables.py`)
Hasil mentah: `backtest/results/bt4-walkforward.json`, log append-only
`backtest/results/bt4-*.jsonl`, trials log `backtest/results/bt4-trials.csv`
(144 trials), log proses `backtest/results/bt4-run.log`.
Engine tests: 26/26 OK (`python3 -m unittest backtest.test_engine`).

Desain metode: docs/STRATEGY_V03.md (S6-T1). Skema window mengikuti brief
tugas S6-T2 (rolling 2 tahun fit -> 1 tahun test, roll tiap tahun) — BUKAN
skema anchored 12M/3M di dokumen desain. Deviasi ini disengaja dan dicatat:
dengan hanya 6 tahun data, rolling 2y/1y menghasilkan 4 fold OOS non-overlap.
Purge gap 2 hari diterapkan di setiap batas IS->OOS (sinyal yang dibuat dalam
2 hari pertama tahun OOS dibuang, mencegah leakage window indikator M15).

## Metode

- Strategi dasar: v0.2 (SMC MSS M15 + regime filter EMA20/50-vs-ATR14 +
  filter news sintetis NFP/CPI), dieksekusi via backtest/engine.py dengan
  komisi $7/lot round-turn, swap, slippage base 1.0 pt (3x di window news).
- Grid parameter: RR TP = {1.5, 2.0, 2.5, 3.0} — satu-satunya parameter yang
  di-"fit" di IS; pilihan terbaik IS diterapkan apa adanya di OOS tahun
  berikutnya. Semua konfigurasi (termasuk yang kalah) dicatat di
  bt4-trials.csv. CATATAN: total 144 trials > anggaran 50 konfigurasi dari
  S6-T1 (grid dijalankan per varian per fold, bukan global) — ini sendiri
  adalah temuan: multiple testing pada 6 tahun data sudah melewati batas
  MinBTL, sehingga p_adj akan sangat konservatif.
- Plateau/cliff check 1-D: tetangga grid (RR +-1 langkah) dari parameter
  terpilih tidak boleh berubah tanda atau jatuh > 40% dari optimum IS.
- Trials >= 50 berarti DSR/Bonferroni formal tidak dihitung di sini —
  dicatat sebagai keterbatasan, bukan disembunyikan.

## Varian regime filter (dari kandidat S6-T1)

| Varian | Definisi | Parameter tambahan |
|--------|----------|--------------------|
| base   | v0.2 apa adanya (EMA spread regime) | 0 |
| session| base + killzone: entry hanya 07:00-10:00 / 12:00-15:00 UTC | 0 (jam fix dari literatur) |
| atrpct | base + vol regime: ATR%(14) <= MA100(ATR%) | 1 (rel 1.0) |
| adx    | base + ADX(14) >= 25 | 1 (threshold 25, default populer — rawan overfit) |

## Tabel fold (IS best RR -> OOS)

STATUS: BACKTEST / NOT VERIFIED

| Fold | IS | OOS | Varian | IS grid 1.5/2.0/2.5/3.0 (R) | Best RR | IS best (R) | OOS @best RR (R) | Degradasi (R) | ODR | OOS trades | OOS WR% | Cliff |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| f1-2020-2022 | 2020-2021 | 2022 | base (v0.2 regime) | +5.18/-2.57/-3.25/+0.63 | 1.5 | +5.18 | -10.75 | -15.93 | -2.08 | 18 | 16.67 | YA |
| f2-2021-2023 | 2021-2022 | 2023 | base (v0.2 regime) | -15.86/-13.69/-15.54/-17.53 | 2.0 | -13.69 | -4.39 | +9.30 | n/a | 31 | 29.03 | YA |
| f3-2022-2024 | 2022-2023 | 2024 | base (v0.2 regime) | -20.93/-15.67/-8.97/-22.16 | 2.5 | -8.97 | +1.79 | +10.77 | n/a | 36 | 30.56 | YA |
| f4-2023-2025 | 2023-2024 | 2025 | base (v0.2 regime) | -10.88/-4.75/+1.56/-13.76 | 2.5 | +1.56 | +11.57 | +10.01 | 7.41 | 138 | 32.61 | YA |
| f1-2020-2022 | 2020-2021 | 2022 | + session killzone | -1.86/+4.24/-20.20/-18.75 | 2.0 | +4.24 | +9.50 | +5.26 | 2.24 | 72 | 40.28 | YA |
| f2-2021-2023 | 2021-2022 | 2023 | + session killzone | -0.75/+14.02/+5.37/+6.35 | 2.0 | +14.02 | -5.28 | -19.30 | -0.38 | 23 | 26.09 | YA |
| f3-2022-2024 | 2022-2023 | 2024 | + session killzone | -5.30/+4.22/+13.23/+12.13 | 2.5 | +13.23 | -4.59 | -17.82 | -0.35 | 16 | 18.75 | YA |
| f4-2023-2025 | 2023-2024 | 2025 | + session killzone | -11.02/-12.18/-5.78/-5.23 | 3.0 | -5.23 | +13.27 | +18.49 | n/a | 50 | 32.00 | YA |
| f1-2020-2022 | 2020-2021 | 2022 | + ATR% vol regime | +1.85/-4.03/+17.65/+36.00 | 3.0 | +36.00 | -9.21 | -45.22 | -0.26 | 16 | 12.50 | YA |
| f2-2021-2023 | 2021-2022 | 2023 | + ATR% vol regime | -17.29/-14.18/-8.86/-7.91 | 3.0 | -7.91 | -1.03 | +6.88 | n/a | 32 | 25.00 | YA |
| f3-2022-2024 | 2022-2023 | 2024 | + ATR% vol regime | -17.19/-19.27/-11.86/-10.24 | 3.0 | -10.24 | -11.47 | -1.23 | n/a | 23 | 13.04 | YA |
| f4-2023-2025 | 2023-2024 | 2025 | + ATR% vol regime | -15.89/-19.12/-11.31/-12.50 | 2.5 | -11.31 | +26.00 | +37.31 | n/a | 143 | 35.66 | YA |
| f1-2020-2022 | 2020-2021 | 2022 | + ADX(14)>=25 | -6.45/+3.31/+3.36/+6.29 | 3.0 | +6.29 | +19.61 | +13.32 | 3.12 | 83 | 32.53 | YA |
| f2-2021-2023 | 2021-2022 | 2023 | + ADX(14)>=25 | -6.10/+1.73/+9.39/+19.25 | 3.0 | +19.25 | -8.33 | -27.58 | -0.43 | 26 | 19.23 | YA |
| f3-2022-2024 | 2022-2023 | 2024 | + ADX(14)>=25 | -9.72/-2.15/+8.30/+11.28 | 3.0 | +11.28 | +1.92 | -9.35 | 0.17 | 16 | 25.00 | tidak |
| f4-2023-2025 | 2023-2024 | 2025 | + ADX(14)>=25 | -14.19/-6.29/-3.25/-6.41 | 2.5 | -3.25 | +16.26 | +19.51 | n/a | 92 | 35.87 | YA |

(n/a pada ODR = IS agregat <= 0, rasio tidak bermakna.)

## Tabel agregat robustness

STATUS: BACKTEST / NOT VERIFIED

| Varian | IS agregat (R) | OOS stitched (R) | WFE (OOS/IS) | Segmen OOS positif | Cliff count | Urutan RR terpilih |
|---|---|---|---|---|---|---|
| base (v0.2 regime) | -15.92 | -1.78 | n/a | 2/4 | 4 | 1.5, 2.0, 2.5, 2.5 |
| + session killzone | +26.27 | +12.90 | 0.49 | 2/4 | 4 | 2.0, 2.0, 2.5, 3.0 |
| + ATR% vol regime | +6.54 | +4.29 | 0.66 | 1/4 | 4 | 3.0, 3.0, 3.0, 2.5 |
| + ADX(14)>=25 | +33.57 | +29.46 | 0.88 | 3/4 | 3 | 3.0, 3.0, 3.0, 2.5 |

## Kesimpulan jujur (kriteria GO/STOP sesuai docs/STRATEGY_V03.md bagian 4)

**TIDAK ROBUST — kriteria STOP terpicu. Iterasi rule-based v0.x sebaiknya
dihentikan; fokus pindah ke Fase 2 (verifikasi forward/demo).**

- Hanya varian ADX yang lolos WFE >= 0.5 (0.88) DAN majority-pass (3/4 = 75%
  segmen OOS positif). Session WFE 0.49 (gagal tipis), atrpct hanya 1/4
  segmen positif (gagal), base IS agregat negatif (gagal total).
- TETAPI varian ADX gagal kriteria plateau/cliff: cliff veto terpicu di 3/4
  fold (tetangga grid RR berubah tanda atau jatuh > 40% dari optimum IS).
  Grid 1-D RR kita memang sempit (4 titik), jadi "cliff" di sini sebagian
  artefak resolusi grid — namun justru itu poinnya: pada grid yang kasar,
  optimum tidak berada di plateau yang stabil.
- OOS stitched ADX +29.46R didominasi fold 2022 (+19.61R) — pola yang sama
  dengan S5-T3: hasil agregat digerakkan satu periode pasar, bukan edge
  stabil. 2025 juga menyumbang +16.26R; dua fold tengah net negatif.
- Urutan RR terpilih melompat (3.0 -> 3.0 -> 3.0 -> 2.5 untuk ADX; bergantung
  varian) — tidak ada konvergensi parameter antar window.
- 144 trials jauh melewati anggaran ~50 konfigurasi (S6-T1, MinBTL): bahkan
  jika WFE lolos, DSR setelah koreksi multiple testing hampir pasti tidak
  signifikan untuk hasil sekecil ini. DSR formal tidak dihitung — keterbatasan
  dicatat, bukan disembunyikan.
- ADX >= 25 adalah threshold default populer: memilihnya sebagai "pemenang"
  dari 4 varian yang diuji adalah multiple testing tambahan yang harus
  dihitung terhadap klaim apapun.

Rekomendasi konkret:
1. Jangan naikkan risiko berdasarkan hasil ini; jangan produksikan EA v0.3
   dengan parameter ADX.
2. Kriteria stop S6-T1 (tanpa plateau / veto katastropik / trials melewati
   budget) terpicu — hentikan iterasi rule-based v0.x, alihkan ke Fase 2
   verifikasi pihak ketiga (Myfxbook/MQL5) seperti direncanakan.
3. Jika nanti dilanjutkan: butuh lebih banyak data (10+ tahun), grid 2-D
   penuh dengan heatmap plateau, dan DSR formal — bukan penambahan filter.

Semua output tetap berlabel BACKTEST / NOT VERIFIED.
