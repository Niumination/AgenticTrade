# AgenticTrade

Sistem trading otomatis berbasis agen AI (analisis **SMC/ICT**) dengan eksekusi MT5,
dibangun di atas satu prinsip inti: **transparansi penuh dan dapat diverifikasi** —
bukan klaim sendiri.

> **Status verifikasi:** Seluruh angka performa di repo ini berstatus
> **backtest/forward-test internal — BUKAN track record real**.
> Cara mengaudit setiap klaim: lihat [`docs/VERIFICATION.md`](docs/VERIFICATION.md).

## Prinsip Non-Negotiable

1. **Terbuka secara default** — kode, kebijakan risiko, dan dokumentasi proses dipublikasikan di repositori.
2. **Semua sinyal dicatat append-only** dengan reasoning lengkap (kenapa entry, SL, TP).
3. **Pagar risiko berada di EA (hard-coded), bukan di AI.** Input AI tidak dapat melewati batas risiko.
4. **Verifikasi atas kepercayaan** — klaim apa pun tentang status atau perilaku sistem dirujuk ke dokumen verifikasi: lihat [`docs/VERIFICATION.md`](docs/VERIFICATION.md).
5. **Tanpa klaim performa** — kami tidak mempublikasikan angka profit atau return sebagai ajakan. Track record diverifikasi pihak ketiga (Myfxbook / MQL5 Signals), bukan tear-sheet buatan sendiri.
6. **Transparansi kegagalan** — drawdown, losing streak, dan periode loss dipublikasikan apa adanya.
7. **Tidak mengelola dana orang lain.** User menjalankan EA/sinyal di akunnya sendiri. AgenticTrade bukan nasihat keuangan; tidak ada janji keuntungan.

## Arsitektur

```
analysis/      modul analisis (Python) — parser sinyal JSON + indikator struktur
               SMC/ICT (swing, Order Block, FVG, MSS); suite pytest
backtest/      engine backtest event-driven per-tick (simulasi fill bid/ask
               Dukascopy, SL-first konservatif, gap refusal) + tooling dataset
ea/            EA MT5 (MQL5) — eksekusi + enforcement hard-coded pagar risiko
               (RISK.md): 1%/posisi, 3% loss harian, kill switch DD 10%
dashboard/     tear-sheet publik otomatis, digenerate dari signals/ (stdlib-only)
signals/       log keputusan AI (JSON append-only, per hari)
docs/          STRATEGY.md (SMC/ICT top-down) · RISK.md (pagar hard-coded) ·
               VERIFICATION.md (cara audit klaim)
.github/       CI: validasi sinyal + regenerate dashboard tiap commit
```

Alur kerja: analisis bias HTF → POI (Order Block/FVG) → konfirmasi MSS → entry,
dengan pagar risiko yang di-enforce di lapisan EA — bukan di AI.

## Fase

- [x] **Fase 0 — Fondasi**: dokumentasi publik (`docs/`), kebijakan transparansi, dokumen verifikasi (`docs/VERIFICATION.md`), aturan kerja multi-bot (`AGENTS.md`).
- [x] **Fase 1a — Fondasi teknis**: prototipe EA dengan pagar risiko hard-coded, modul analisis + suite pytest, engine backtest internal (dataset tick XAUUSD 2020–2025).
- [ ] **Fase 1b — Demo + dashboard audit publik**: EA jalan di **demo**, dashboard audit publik dari `signals/` sejak hari pertama, verifikasi pihak ketiga (Myfxbook/FXBlue read-only) **menyusul**.
- [ ] **Fase 2 — Track record terverifikasi**: akun real kecil via MQL5 Signals/Myfxbook; perbaikan berdasarkan data.
- [ ] **Fase 3 — Partisipasi komunitas**: beta pengguna awal (user jalankan di akunnya sendiri), mekanisme masukan publik.

> Status terkini tiap fase mengikuti dokumen di repositori (terutama
> `docs/VERIFICATION.md`), bukan halaman ini.

## Latar Belakang

Riset terhadap sistem serupa yang beredar (mis. Phantom Intelligence — XAUUSD,
multi-agent AI + MT5 auto-trade) menunjukkan pola umum: tear-sheet klaim mandiri
tanpa verifikasi pihak ketiga, track record pendek, dan angka yang tidak konsisten
antar halaman. AgenticTrade dibangun dengan arah berlawanan: **kredibilitas dibangun
oleh waktu + data yang tidak bisa dimanipulasi**, bukan oleh klaim.

## Disclaimer

Proyek ini adalah tools & otomasi untuk akun milik pengguna sendiri, untuk tujuan
transparansi dan edukasi. Bukan ajakan investasi, bukan pengelolaan dana, bukan
nasihat keuangan, tidak ada jaminan keuntungan. Trading forex berisiko tinggi;
bagi penduduk Indonesia, gunakan broker berizin Bappebti/COFITTO.
