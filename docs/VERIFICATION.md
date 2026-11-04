# VERIFICATION — Cara Audit Track Record

> Kredibilitas sistem ini dibangun oleh verifikasi pihak ketiga, bukan klaim sendiri.
> Selama tautan verifikasi belum ada di halaman ini, SELURUH angka performa di repo
> ini berstatus **backtest/forward-test internal — BUKAN track record real**.

## Standar Verifikasi (berlaku bertahap)

| Fase | Sarana verifikasi | Status |
|------|-------------------|--------|
| Fase 1 (demo) | Dashboard otomatis dari `signals/` (append-only) + CI regenerate per commit | ⏳ belum |
| Fase 1–2 (demo) | **Myfxbook** / **FXBlue** akun demo terhubung investor password (read-only) | ⏳ belum |
| Fase 2 (real kecil) | **MQL5 Signals** atau Myfxbook akun real | ⏳ belum |

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
