# STRATEGY — Kerangka SMC/ICT Top-Down (Fase 0 Draft)

> Dokumen hidup. Setiap perubahan strategi wajib dicatat di changelog bawah
> dan tidak berlaku surut untuk sinyal yang sudah tercatat.

## Model Setup Utama

### 1. Sniper Desk — Order Block M15 → MSS M1
- **HTF (H4/D1):** tentukan bias (bullish/bearish) via struktur swing + premium/discount
- **M15:** cari POI = Order Block / FVG searah bias, di zona premium (sell) atau discount (buy)
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
