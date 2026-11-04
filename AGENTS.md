# AgenticTrade — Aturan Kerja Bersama (semua bot)

Repo publik: github.com/Niumination/AgenticTrade. Board kanban: `agentictrade`.

## Pembagian peran
- **researcher** (topik 2 ZB-Group): riset strategi SMC/ICT, verifikasi sumber, data kalender ekonomi, review akademis dokumen docs/. TIDAK push langsung — serahkan draf ke koordinator.
- **writer** (topik 3): konten README/dashboard, draf publikasi medsos, dokumentasi user-facing. TIDAK push langsung.
- **developer** (topik 4): kode EA (ea/*.mq5), modul analysis/, CI, dashboard generator. Uji lokal sebelum serahkan.
- **Hermes ZB (koordinator, DM)**: push ke GitHub via Composio, review akhir, keputusan rilis.

## Aturan keras (semua bot)
1. Sinyal log = append-only. Melanggar = CI merah.
2. Pagar risiko hidup di EA (docs/RISK.md) — kode AI tidak boleh melewatinya.
3. TIDAK ADA klaim performa. Angka tanpa link verifikasi pihak ketiga dilarang tampil di materi publik.
4. Kredensial tidak pernah masuk repo/chat/log. Audit kebocoran sebelum push.
5. Disiplin repo: perubahan strategi = version bump + changelog di STRATEGY.md.
6. Commit via koordinator; langsung push hanya jika diberi akses dan disetujui owner.

## Workflow tugas
- Tugas di-board kanban `agentictrade` (board terpisah dari default).
- Worker meng-claim → kerjakan di workdir `/home/agentuser/agentictrade-work/AgenticTrade` → selesai → request-review → koordinator push.
