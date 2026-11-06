# AgenticTrade — Panduan Setup Fase 2: Akun Demo MT5 + Myfxbook EA Publisher

Dokumen operasional untuk user (persiapan manual). Disusun dari checklist S5-T1
(koordinator) dan riset S4-T3. Data expiry/leverage demo diverifikasi 2026-11-05.

> Catatan penting: dokumen ini TIDAK berisi klaim performa apa pun. Semua hasil
> demo hanyalah data pengujian — bukan indikasi hasil live. Lihat
> docs/VERIFICATION.md untuk status verifikasi aktual.

---

## 1. Rekomendasi broker demo (1 pilihan final)

**Pilihan final: IC Markets (demo MT5).**

Alasan:
- Expiry demo paling longgar yang terverifikasi: 30 hari berdasarkan inaktivitas
  (cukup login + trade minimal 1x per bulan agar akun tidak expire). Pepperstone
  60 hari sejak pembuatan juga bagus, tetapi IC Markets lebih mudah diperpanjang
  dengan aktivitas.
- Spread XAUUSD pada Raw Account termasuk yang terbaik dari kandidat
  (IC Markets / Pepperstone / Tickmill / Exness) — penting karena EA berdagang
  XAUUSD di M15 dan hasil sangat sensitif terhadap spread.
- Tanpa KYC untuk akun demo; leverage demo bisa dipilih hingga 1:1000
  (tergantung entitas regulasi; entitas FSA max 1000:1).
- Didukung penuh Myfxbook EA Publisher; nama server resmi terdaftar jelas
  (contoh: `ICMarketsSC-MT5`), sehingga koneksi verifikasi pihak ketiga mulus.

Alternatif jika IC Markets bermasalah: Pepperstone (60 hari, server
`Pepperstone-Demo`). Hindari Tickmill untuk Fase 2 (demo expire 7 hari tanpa
login — mudah kehilangan history). Exness boleh, tapi demo MT5-nya dihapus
setelah 21 hari tanpa LOGIN dan unlimited leverage-nya hanya efektif saat
equity < $5,000.

---

## 2. Buka akun demo MT5 — langkah persis

1. Buka Client Area IC Markets (icmarkets.com), daftar dengan email aktif.
   Untuk demo tidak ada KYC.
2. Buat akun demo **MT5** (bukan MT4):
   - Platform: MetaTrader 5
   - Tipe akun: **Raw Spread** (spread XAUUSD terbaik; komisi tetap terhitung
     realistis)
   - Currency: **USD**
   - Leverage: **1:500**
   - Balance: **$1,000** — samakan dengan rencana modal live yang direncanakan.
     Jangan pakai $1,000,000: ukuran lot jadi tidak realistis dan psikologi
     pengujian menyesatkan.
3. Setelah dibuat, **catat tiga hal** (wajib untuk Myfxbook nanti):
   - LOGIN (angka akun)
   - Password (master/trading)
   - SERVER persis seperti yang ditampilkan (mis. `ICMarketsSC-MT5`)
4. Simbol yang dipakai: **XAUUSD** (gold). Pastikan muncul di Market Watch dan
   buka chart-nya. EA ini prototipe satu simbol — sinyal hanya dieksekusi pada
   simbol chart yang juga ada di daftar simbol diizinkan EA.

Catatan lot: EA mengelola lot lewat guard risiko bawaan (maks 1% ekuitas per
posisi, hard-coded — bukan input user). Volume minimal broker 0.01 sudah
memadai untuk balance $1,000.

---

## 3. Download MT5 + login

1. Download MT5 versi broker dari Client Area IC Markets (paling aman — server
   sudah terdaftar), atau dari metatrader5.com lalu tambahkan server manual.
2. Install di Windows (atau VPS Windows; MT5 tidak berjalan native di Linux/macOS).
3. Login: **File → Connect to Trade Account** → isi:
   - Login: nomor akun demo
   - Password: password trading (bukan investor)
   - Server: persis seperti tercatat (mis. `ICMarketsSC-MT5`)
   - Centang **Save password**
4. Cek koneksi: pojok kanan bawah terminal harus hijau dengan latency, dan
   balance $1,000 muncul di tab Trade.

---

## 4. Compile EA di MetaEditor + attach ke chart XAUUSD M15

1. Salin file EA: di MT5 → **File → Open Data Folder** → masuk ke
   `MQL5\Experts\` → salin `AgenticTrade.mq5` (dari repo, folder `ea/`) ke sana.
2. Buka MetaEditor: di MT5 tekan **F4** (Tools → MetaQuotes Language Editor).
3. Di MetaEditor buka `AgenticTrade.mq5` (panel Navigator → Experts) → tekan
   **F7 (Compile)**.
   - Target: **0 errors, 0 warnings**.
   - Jika error: pastikan build MT5 terbaru (Help → About), dan file
     `Trade/Trade.mqh` include bisa ditemukan (default include path standar).
4. Kembali ke MT5. Buka chart **XAUUSD, timeframe M15**.
5. Di Navigator (Ctrl+N) → Experts → drag **AgenticTrade** ke chart XAUUSD M15.
   - Tab **Common**: centang **Allow Algo Trading**.
   - Tab **Inputs**: EA memakai guard hard-coded (1% per posisi, 3% loss harian
     stop, 10% DD kill switch, maks 2 posisi, blok news ±15 menit). Nilai-nilai
     ini **tidak boleh diubah** — jangan berikan input baru yang melewati guard.
   - OK.
6. Verifikasi:
   - Tombol **Algo Trading** di toolbar berwarna **HIJAU**.
   - Tab **Experts/Journal** menampilkan log init EA tanpa error.
   - EA akan menolak eksekusi di luar simbol diizinkan (XAUUSD/EURUSD/GBPUSD),
     di luar killzone untuk setup 2, atau saat file kalender news lebih tua dari
     2 jam — itu perilaku fail-safe yang benar, bukan bug.

---

## 5. Myfxbook EA Publisher + verifikasi

1. Prasyarat: Windows dengan .NET Framework 4.0+; MT5 berjalan dan login;
   PC/VPS harus tetap menyala selama pasar buka (data kontinu butuh koneksi
   24/5 — pertimbangkan VPS Windows kecil).
2. Buat akun di myfxbook.com.
3. Download **EA Publisher** resmi: myfxbook.com → bagian AutoTrade / Track
   Record → EA Publisher.
4. Install dan jalankan Publisher → masukkan kredensial akun myfxbook.
5. Tambah akun di Publisher:
   - Platform: **MT5**
   - Account number: nomor demo
   - Password: **master password** (Publisher memverifikasi akun dengan master;
     investor password dipakai bila diminta kredensial read-only — MT5:
     klik kanan akun → ubah investor password)
   - Server: **ketik manual, persis** seperti di MT5 (mis. `ICMarketsSC-MT5`)
6. Verifikasi:
   - Status Publisher: **Connected / Running**.
   - Di dashboard myfxbook, akun muncul dengan tanda **verified (hijau)**.
   - Data biasanya ter-update sekitar per 1 menit selama MT5 online.
   - Cek equity curve mulai terisi; bandingkan dengan Journal MT5 bila ada
     selisih.

---

## 6. Hal yang TIDAK boleh dilakukan

1. **Jangan pakai akun real dulu.** Fase 2 murni demo. Semua pemindahan ke
   live harus lewat keputusan terpisah dengan kriteria yang sudah ditetapkan —
   bukan karena hasil demo terlihat bagus.
2. **Jangan ubah guard EA.** Nilai berikut hard-coded dan non-negotiable
   (docs/RISK.md): 1% risiko per posisi, 3% loss harian → stop hari itu,
   10% DD dari HWM → kill switch total, maks 2 posisi paralel, blok news ±15
   menit, SL wajib, simbol hanya XAUUSD/EURUSD/GBPUSD. Jangan edit konstanta di
   source, jangan tambah input yang melewati guard, jangan patch binary.
3. Jangan jalankan EA di simbol lain (prototipe satu simbol: XAUUSD).
4. Jangan matikan "Allow Algo Trading" lalu mengira EA tetap bekerja — jika
   tombol Algo Trading merah, EA tidak akan mengeksekusi apa pun.
5. Jangan hapus/reset akun demo saat sudah terhubung ke Myfxbook tanpa
   mencatatnya — history track record demo akan hilang dan grafik terputus.
6. Jangan menyebarkan screenshot hasil demo sebagai klaim performa di mana pun.
   Semua publikasi tetap merujuk docs/VERIFICATION.md (status: NOT VERIFIED
   sampai ada verifikasi pihak ketiga).
7. Jangan berikan master password ke pihak lain; untuk read-only gunakan
   investor password.

---

## Lampiran: perbandingan broker demo (verifikasi 2026-11-05)

| Broker | Expiry demo | Leverage | Catatan |
|---|---|---|---|
| IC Markets | 30 hari inaktivitas | s.d. 1:1000 (tergantung entitas) | Spread raw XAUUSD terbaik; tanpa KYC demo; **pilihan final** |
| Pepperstone | 60 hari sejak pembuatan | s.d. 1:1000 (FCA 1:500 di beberapa entitas) | Alternatif kuat; non-expiry bila punya akun live funded |
| Tickmill | 7 hari tanpa login | 1:500 (gold = leverage akun); selected symbols s.d. 1:1000 | Expiry paling ketat; maks 7 demo/email; hanya jika disiplin login mingguan |
| Exness | Demo MT5 dihapus 21 hari tanpa LOGIN | s.d. 1:unlimited (efektif saat equity < $5,000) | XAUUSD eligible (kecuali XAUUSD247) |

Sumber: panduan setup S5-T1 (riset S4-T3, help centre broker, diverifikasi
2026-11-05).
