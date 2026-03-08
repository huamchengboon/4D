# Where your 256 GB is used — breakdown

**Disk:** ~251 GB physical (256 GB marketed)  
**Free now:** ~85 GB (on main data volume)  
**Used:** ~118 GB on Data + ~12 GB system + ~14 GB other volumes = **~144 GB total used**

---

## 1. APFS container (~245 GB)

| Volume | Size (used) | What it is |
|--------|-------------|------------|
| **Macintosh HD - Data** | **118 GB** | Your files, apps, user data (this is the main one) |
| **Macintosh HD** (system) | **12 GB** | macOS system (read-only snapshot, OS files) |
| **Preboot** | **9 GB** | Boot loaders, recovery helpers |
| **VM** | **4 GB** | Swap / sleep image (RAM on disk) |
| **Recovery** | **1.4 GB** | macOS recovery |
| **Free (Data)** | **85 GB** | Available space |

---

## 2. Data volume (118 GB) — where your “used” data lives

| Category | Size | Contents |
|----------|------|----------|
| **Users (your home)** | **62 GB** | Everything under `/Users/chengboon` |
| **Applications** | **17 GB** | Apps in `/Applications` (Cursor, Arc, Docker, etc.) |
| **private** | **4.3 GB** | `var/vm` (swap ~2 GB), `var/db` (~2.1 GB), `var/folders` (caches ~93 MB) |
| **Library** (on Data) | **4.1 GB** | System-level Library (not your user Library) |
| **Other** | **~31 GB** | `usr`, `opt`, `.Spotlight-V100`, `.fseventsd`, system caches, etc. |

---

## 3. Your home folder (62 GB) — detail

From earlier scans, the main parts of `~/`:

| Folder | Approx. size | What it is |
|--------|----------------|------------|
| **Library** | **~27 GB** | App support, caches, containers |
| **Library/Application Support** | ~15 GB | Cursor 7.5G, Arc 2.7G, Razer 1.5G, Code, etc. |
| **Library/Containers** | ~5.5 GB | Docker 3.6G, OneDrive, Teams, WhatsApp, etc. |
| **Library/Group Containers** | ~4.8 GB | WhatsApp 4G, Office, OneDrive sync |
| **Library/Caches** | ~1.5 GB | Cursor ShipIt, Adobe, Siri, etc. |
| **Projects** | **~5–6 GB** | Your code (after node_modules/venv cleanup) |
| **.cursor** | **~2.2 GB** | Cursor extensions, chats |
| **Downloads** | ~2.8 GB | |
| **Documents** | ~0.9 GB | |
| **Desktop, .npm, .cache, .cargo, .rustup, etc.** | ~3–4 GB | |
| **Rest of home** | ~18 GB | Config, other apps, hidden folders |

---

## 4. Summary picture

```
256 GB disk (251 GB usable)
├── Data volume USED: 118 GB
│   ├── Your home (Users/chengboon): 62 GB
│   │   ├── Library (app data, containers, caches): ~27 GB
│   │   ├── Projects: ~5–6 GB
│   │   ├── .cursor: ~2.2 GB
│   │   └── Downloads, Documents, rest: ~27 GB
│   ├── Applications: 17 GB
│   ├── System private/var (vm, db, caches): 4.3 GB
│   ├── Library (Data): 4.1 GB
│   └── Other (system): ~31 GB
├── System volume (macOS): 12 GB
├── Preboot + Recovery + VM: ~14 GB
└── FREE: 85 GB (on Data)
```

---

## 5. Biggest single consumers (for freeing space)

1. **Your Library** (~27 GB) — Cursor, Arc, WhatsApp, Docker data, etc.  
2. **Applications** (17 GB) — Uninstall unused apps.  
3. **“Other” on Data** (~31 GB) — System caches, Spotlight, etc.; some reclaimable via “Optimize” or cleanup.  
4. **Projects** (~5–6 GB) — Already reduced; can trim more by removing old repos or `node_modules`/`.venv`.  
5. **Cursor** (~7.5 GB in Library + ~2.2 GB in .cursor) — Clear Cursor caches / remove extensions to shrink.

---

*Numbers are from `df`, `diskutil`, and `du`; “Other” is the remainder on the Data volume.*
