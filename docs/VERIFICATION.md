# VERIFICATION — Cara Audit Track Record

> Kredibilitas sistem ini dibangun oleh verifikasi pihak ketiga, bukan klaim sendiri.
> Selama tautan verifikasi belum ada di halaman ini, SELURUH angka performa di repo
> ini berstatus **backtest/forward-test internal — BUKAN track record real**.

# HASIL BACKTEST FASE 1 — INTERNAL ONLY

## ⚠️ NOT VERIFIED ⚠️

**Semua angka di bawah ini adalah hasil backtest internal yang berjalan pada dataset
tick XAUUSD 2020–2025 dengan asumsi fill yang disederhanakan. Statusnya
`NOT VERIFIED`: belum ada verifikasi pihak ketiga (Myfxbook/FXBlue/MQL5), belum ada
eksekusi demo maupun real. Jangan menganggap angka ini sebagai prediksi performa.**

Sumber data mentah: [`backtest/results/bt1-summary.json`](../backtest/results/bt1-summary.json)
(log per trade per tahun: `backtest/results/bt1-YYYY.jsonl`).

## Ringkasan per tahun (modal awal 10.000, strategi v0.1)

| Tahun | Trade eksekusi | Win rate | Total R | Expectancy (R/trade) | Equity akhir | Max DD % | Loss beruntun terpanjang |
|-------|---------------|----------|---------|----------------------|--------------|----------|--------------------------|
| 2020  | 75            | 34.67%   | +0.72   | +0.0097              | 10.047,29    | 10.11%   | 8                        |
| 2021  | 60            | 35.00%   | +1.75   | +0.0291              | 10.110,50    | 8.97%    | 8                        |
| 2022  | 162           | 34.57%   | +1.63   | +0.0101              | 10.025,24    | 11.43%   | 12                       |
| 2023  | 63            | 31.75%   | **−3.00** | −0.0476            | 9.667,70     | 8.38%    | 7                        |
| 2024  | 67            | 34.33%   | **−4.96** | −0.0740            | 9.473,92     | 11.54%   | 10                       |
| 2025  | 107           | 30.84%   | **−11.22** | −0.1049           | 8.870,78     | 11.29%   | 10                        |
| **Total** | **534**   | ~33.5%   | **−15.08** | **−0.0282**       | —            | —        | 12                        |

### Bacaan jujur atas angka tersebut

- **Kumulatif, strategi v0.1 rugi** (± −15R per 10.000 unit modal awal per tahun,
  dieksekusi berurutan). Tiga dari enam tahun positif dengan edge yang sangat tipis
  (+0.72R sampai +1.75R per tahun), tiga tahun terakhir negatif dan memburuk.
- **Kill switch 10% terpicu di SETIAP tahun** — drawdown maksimum menyentuh atau
  melampaui batas 10% di keenam tahun (8.38%–11.54%).
- Tidak ada tahun yang menghasilkan profit material setelah biaya penuh; lihat
  batasan metodologi di bawah — biaya belum dimodelkan lengkap, sehingga angka di
  atas kemungkinan **overstate** performa.
- Kesimpulan yang didukung data: strategi v0.1 **belum layak dijalankan** pada akun
  mana pun. Iterasi v0.2 (biaya penuh + filter regime) dan v0.3 (walk-forward
  optimization, 144 trials, 4 varian filter) telah dijalankan — hasilnya juga
  **TIDAK robust**: out-of-sample stitched terbaik (+29,46R varian ADX) gagal
  plateau/cliff check dan didominasi satu periode pasar (2022). Kriteria STOP
  terpicu — lihat [`docs/ROBUSTNESS.md`](docs/ROBUSTNESS.md) dan
  [`docs/WALKFORWARD.md`](docs/WALKFORWARD.md). Iterasi rule-based v0.x
  dihentikan; proyek beralih ke **Fase 2** (verifikasi forward via akun demo +
  Myfxbook, panduan di [`docs/FASE2_SETUP_ID.md`](docs/FASE2_SETUP_ID.md)).

# Batasan Metodologi

Dari review akademis internal (S3-T4) terhadap `backtest/engine.py` dan
`dashboard/generate.py`. Batasan-batasan ini berarti angka backtest di atas harus
dibaca dengan skeptisisme ekstra:

1. **Biaya belum lengkap.** Swap dan komisi belum dimodelkan. Untuk XAUUSD swap
   umumnya negatif dan material; hasil di atas belum memasukkan keduanya.
2. **Dua sumber kebenaran metrik R.** Engine menulis `result.pnl_r`, sedangkan
   dashboard menghitung ulang R dari entry/sl/tp sinyal (bukan fill aktual) —
   angka tear sheet dashboard bisa berbeda dari metrik engine.
3. **Fallback +2R di dashboard** saat RR tak bisa dihitung adalah fabrikasi data;
   seharusnya error. Perbaikan masuk backlog.
4. **Bug end-of-data**: outcome `sl` dipaksa −1R padahal exit aktual bisa berbeda
   dari jarak SL.
5. **Slippage gap pada SL** selama posisi terbuka tidak dimodelkan (fill diasumsikan
   pada level SL).
6. Temuan minor: klasifikasi breakeven tidak konsisten antara engine dan dashboard,
   statistik disortir by `created_at` bukan `closed_at`, timestamp sinyal == tick
   edge, kalender hari UTC vs roll 5pm ET.

Sisi yang sudah konservatif-by-design: entry T+1 (tanpa same-tick fill), SL menang
ties saat SL/TP kena tick yang sama, risk guards hard-coded dengan audit trail
`blocked_reason`, output append-only dengan banner NOT VERIFIED.

# Roadmap Verifikasi

| Fase | Sarana verifikasi | Status |
|------|-------------------|--------|
| Fase 1 (internal) | Backtest internal + dashboard otomatis dari `signals/` (append-only) + CI regenerate per commit | ✅ backtest selesai (hasil di atas, NOT VERIFIED) |
| Fase 1b–2 (demo) | **Myfxbook** / **FXBlue** akun demo terhubung investor password (read-only) | ⏳ belum |
| Fase 2 (real kecil) | **MQL5 Signals** atau Myfxbook akun real | ⏳ belum |

**Verifikasi pihak ketiga via Myfxbook/MQL5 adalah gerbang wajib Fase 2.** Selama
tautan verifikasi belum terpasang, tidak ada angka di repo ini yang boleh
diperlakukan sebagai track record.

## Komitmen Transparansi
1. Dashboard menampilkan hasil apa adanya: win rate, drawdown, losing streak, periode loss.
2. Sinyal yang TIDAK dieksekusi (diblok pagar risiko) tetap terlihat di log.
3. Tidak ada penghapusan/backfill log sinyal (append-only, CI memverifikasi histori).
4. Versi strategi aktif dicantumkan di dashboard; statistik tidak digabung antar versi.

## Tautan Verifikasi
(mulai Fase 1: tempatkan link Myfxbook/FXBlue di sini)

- Dashboard internal: _belum tersedia_
- Myfxbook: _belum tersedia_
- MQL5: _belum tersedia_
