# STRATEGY — Kerangka SMC/ICT Top-Down (v0.2)

> Dokumen hidup. Setiap perubahan strategi wajib dicatat di changelog bawah
> dan tidak berlaku surut untuk sinyal yang sudah tercatat.

## Model Setup Utama

### 1. Sniper Desk — Order Block M15 → MSS M1 (v0.2)
- **HTF (H4/D1):** tentukan bias (bullish/bearish) via struktur swing + premium/discount
- **M15:** cari POI = Order Block / FVG searah bias, di zona premium (sell) atau discount (buy)
- **Regime filter (v0.2):** hanya entry saat trendiness `|EMA20 − EMA50| / ATR14 ≥ 0.5`
  DAN arah MSS searah slope EMA — sinyal MSS di pasar ranging (chop) dibuang
- **Filter news (v0.2):** tidak ada sinyal baru di dalam window blokir rilis
  high-impact (analysis/calendar.py; NFP + CPI window historis untuk backtest)
- **M1:** tunggu MSS (Market Structure Shift) sebagai konfirmasi → entry di OB M1 / FVG M1
- **SL:** di bawah/atas OB pelindung; **TP:** liquidity target (equal highs/lows atau struktur M15 berikutnya)
- Minimum RR filter: **1 : 1.8**

### 2. Sweep Hunter — Killzone Liquidity Sweep
- Aktif hanya pada **Killzone London (07:00–10:00 UTC)** dan **NY (12:00–15:00 UTC)**
- Sweep high/low Asia/London sebelumnya → displacement candle → entry di retracement FVG
- **Filter news merah:** tidak ada entry ±15 menit sebelum/sesudah rilis ekonomi high-impact
- Minimum RR filter: **1 : 2.0**

## Aturan Konsistensi
- Satu setup dijalankan sesuai definisi di dokumen ini — tidak ada "vibe trading".
- Setiap sinyal AI wajib mengisi field reasoning dalam log; sinyal tanpa reasoning valid = BUG, bukan fitur.
- Perubahan parameter setup = perubahan versi strategi; hasil lama tidak boleh digabung dengan hasil versi baru dalam satu statistik.

## Changelog
| Versi | Tanggal | Perubahan |
|-------|---------|-----------|
| 0.1 | 2026-11-04 | Draft awal fase 0 (dua setup: Sniper Desk, Sweep Hunter) |
| 0.2 | 2026-11-05 | Sniper Desk + regime filter (EMA20/50 vs ATR14, min 0.5, arah searah MSS) + filter kalender news; RR dieksperimenkan 1.5/2.0/2.5 (RR 2.0 tetap baseline). Engine backtest kini memodelkan komisi ($7/lot round-turn) + swap (Wed 3x) + slippage 3x di window news; exit end-of-data memakai jarak riil (bukan −1R). Konvensi fill T+1 didokumentasikan. Hasil v0.2: BACKTEST / NOT VERIFIED (bt2-summary.json) |
