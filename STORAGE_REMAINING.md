# Storage Rescan — What’s Left After Cleanup

Rescan date: after Docker prune, uv/npm/Bun cache clean, and Wine/Trunk/Whisky removal.

---

## Remaining storage (largest first)

| Rank | Location | Size | Main contents |
|------|----------|------|----------------|
| **1** | **Library/Application Support** | **16 GB** | Cursor 7.9 GB, Arc 2.7 GB, Razer 1.5 GB, Code 573 MB, others |
| **2** | **Projects** | **9.5 GB** | 4D, yoloe, RAPS-1, tracker, office, etc. |
| **3** | **Library/Group Containers** | **4.9 GB** | WhatsApp ~4 GB, Office 437 MB, OneDrive 217 MB, OrbStack 125 MB |
| **4** | **Library/Containers** | **5.9 GB** | Docker 3.6 GB, OneDrive 747 MB, mediaanalysisd 571 MB, Teams 325 MB, WhatsApp 230 MB, Whisky gone |
| **5** | **.cursor** | **2.9 GB** | Extensions 2.8 GB |
| **6** | **Downloads** | **2.8 GB** | Telegram Desktop 881 MB, Social OS 822 MB, zips/DMGs |
| **7** | **.npm** | **948 MB** | _npx cache 933 MB |
| **8** | **Documents** | **868 MB** | Backup_Luna 693 MB, POLI 571 MB |
| **9** | **.rustup** | **1.2 GB** | Rust toolchain |
| **10** | **.cache** | **464 MB** | huggingface 239 MB, prisma 166 MB, taproom 42 MB, nvim/fish/etc. (winetricks & trunk removed) |
| **11** | **.cargo** | **313 MB** | Registry/source cache |
| **12** | **.bun** | **57 MB** | Bin only (cache cleared) |

---

## What changed since the first report

| Item | Before | After | Saved |
|------|--------|--------|--------|
| Docker (Containers) | ~18 GB | 3.6 GB | **~12 GB** (prune) |
| .cache (uv + winetricks + trunk) | 7.4 GB | 464 MB | **~5.5 GB** (uv clean + Wine/Trunk removal) |
| .npm | 4.4 GB | 948 MB | **~3.5 GB** (npm cache clean) |
| .bun | 4.8 GB | 57 MB | **~4.7 GB** (bun pm cache rm) |
| Whisky (Containers) | 452 MB | 0 | **452 MB** (data removed) |
| Library/Containers total | 21 GB | 5.9 GB | **~15 GB** (Docker + Whisky) |

**Rough total freed from your home directory: ~37 GB** (Docker, uv, npm, Bun, Wine/Trunk caches, Whisky).

---

## Biggest remaining (and what you can do)

1. **Application Support (16 GB)** — Cursor, Arc, Razer, Code. Easiest win: remove unused Cursor/VS Code extensions; clear caches in app settings if available.
2. **Projects (9.5 GB)** — Your code and venvs. Shrink only by deleting projects or cleaning `node_modules` / `.venv` / `target` in projects you don’t need.
3. **Group Containers (4.9 GB)** — Mostly WhatsApp. Use WhatsApp → Storage and data to clear media/old chats.
4. **Containers (5.9 GB)** — Docker 3.6 GB (will grow as you use it), OneDrive, etc. Run `docker system prune -a -f` periodically if you use Docker.
5. **.cursor (2.9 GB)** — Remove unused extensions in Cursor.
6. **Downloads (2.8 GB)** — Delete old DMGs, zips, and one-off folders you don’t need.

---

*Rescan done with `dust`; no files were modified.*
