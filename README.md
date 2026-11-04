# AgenticTrade

Sistem trading otomatis berbasis agent AI (analisis **SMC/ICT**) dengan eksekusi MT5
dan track record yang **dapat diaudit publik** — bukan klaim sendiri.

## Prinsip Non-Negotiable

1. **Semua sinyal dicatat append-only** dengan reasoning lengkap (kenapa entry, SL, TP).
2. **Pagar risiko berada di EA (hard-coded), bukan di AI.** Input AI tidak dapat melewati batas risiko.
3. **Track record diverifikasi pihak ketiga** (Myfxbook / MQL5 Signals) — bukan tear-sheet buatan sendiri.
4. **Transparansi kegagalan**: demo 3–6 bulan, lalu real kecil; drawdown, losing streak, dan periode loss dipublikasikan apa adanya.
5. **Tidak mengelola dana orang lain.** User menjalankan EA/sinyal di akunnya sendiri. Tidak ada janji keuntungan.

## Latar Belakang

Riset terhadap sistem serupa yang beredar (mis. Phantom Intelligence — XAUUSD,
multi-agent AI + MT5 auto-trade) menunjukkan pola umum: tear-sheet klaim mandiri
tanpa verifikasi pihak ketiga, track record pendek, dan angka yang tidak konsisten
antar halaman. AgenticTrade dibangun dengan arah berlawanan: **kredibilitas dibangun
oleh waktu + data yang tidak bisa dimanipulasi**, bukan oleh klaim.

## Struktur Repo

```
docs/          STRATEGY.md (SMC/ICT top-down), RISK.md (pagar hard-coded), VERIFICATION.md
signals/       log keputusan AI (JSON append-only, per hari)
ea/            EA MT5 (MQL5) — eksekusi + enforcement pagar risiko
analysis/      modul analisis (Python) — bias HTF → POI → konfirmasi MSS → entry
backtest/      skrip backtest + dataset config
dashboard/     tear-sheet publik otomatis (generate dari signals/)
.github/       CI: validasi sinyal + regenerate dashboard tiap commit
```

## Roadmap

- [ ] **Fase 0** (minggu 1–4) — definisi strategi & aturan risiko tertulis, pilih data & broker uji
- [ ] **Fase 1** (bulan 1–3) — prototipe EA + pipeline sinyal, jalan di **demo**, dashboard audit publik sejak hari pertama
- [ ] **Fase 2** (bulan 3–9) — kumpulkan track record terverifikasi, perbaiki berdasarkan data
- [ ] **Fase 3** — beta pengguna awal (user jalankan di akunnya sendiri)

## Disclaimer

Proyek ini adalah tools & otomasi untuk akun milik pengguna sendiri.
Bukan ajakan investasi, bukan pengelolaan dana, tidak ada jaminan keuntungan.
Trading forex berisiko tinggi; bagi penduduk Indonesia, gunakan broker berizin Bappebti/COFITTO.
