# macOS Home Directory Storage Report

Generated from `dust` scans (list-then-scan approach). All sizes are on-disk. **Nothing was deleted.**

---

## Where your storage went (largest first)

### 1. **Library/Containers — 21 GB**
| Subfolder | Size | Notes |
|-----------|------|--------|
| **Docker (com.docker.docker)** | **18 GB** | Docker images, containers, volumes |
| OneDrive (com.microsoft.OneDrive-mac) | 747 MB | |
| mediaanalysisd | 571 MB | |
| Teams | 325 MB | |
| WhatsApp | 230 MB | (app container; main data in Group Containers) |
| Whisky (Bottles) | 452 MB | |
| Others | ~1.7 GB | |

**→ Biggest single consumer: Docker. Consider `docker system prune` (removes unused images/containers) if you need space.**

---

### 2. **Library/Application Support — 16 GB**
| Subfolder | Size | Notes |
|-----------|------|--------|
| **Cursor** | **7.9 GB** | Cursor IDE app data (extensions, cache, state) |
| Arc | 2.7 GB | Arc browser |
| Razer | 1.5 GB | Razer apps |
| Code (VS Code) | 573 MB | |
| anythingllm-desktop | 511 MB | |
| Kegworks | 508 MB | |
| TabNine | 290 MB | |
| Telegram Desktop | 303 MB | |
| Others | ~2 GB | |

---

### 3. **Projects — 9.5 GB**
| Subfolder | Size |
|-----------|------|
| 4D (this repo) | 1.6 GB (.venv ~1G, target ~575M) |
| yoloe | 1.5 GB |
| RAPS-1 | 1.4 GB |
| tracker | 637 MB |
| office | 553 MB |
| profile | 534 MB |
| local-ai-packaged | 512 MB |
| network-simulator | 495 MB |
| JabilAI-ocr-Kernal-6.12 | 437 MB |
| Others | ~1.5 GB |

---

### 4. **.cache — 7.4 GB**
| Subfolder | Size | Notes |
|-----------|------|--------|
| **uv (archive-v0)** | **4.8 GB** | Python package cache (uv) |
| trunk (tools) | 857 MB | Trunk tooling |
| winetricks (win7sp1) | 903 MB | Wine/Windows runtimes |
| puccinialin (cargo) | 324 MB | Cargo cache |
| Adobe | 319 MB | |
| SiriTTS | 261 MB | |
| GeoServices | 74 MB | |
| Homebrew (taproom) | 42 MB | |
| Others | ~400 MB | |

**→ uv cache is large; safe to clear with `uv cache clean` if you don’t mind re-downloading packages.**

---

### 5. **Library/Group Containers — 4.9 GB**
| Subfolder | Size |
|-----------|------|
| **WhatsApp (Message)** | **~4 GB** |
| Office (SolutionPackages etc.) | 437 MB |
| OneDrive sync client | 217 MB |
| OrbStack | 125 MB |
| Others | ~130 MB |

---

### 6. **.bun — 4.8 GB**
| Subfolder | Size |
|-----------|------|
| **install/cache** | **4.8 GB** |
| bin | 57 MB |

**→ Bun global cache. You can clear with `bun pm cache rm` if needed.**

---

### 7. **.npm — 4.4 GB**
| Subfolder | Size |
|-----------|------|
| **_cacache (content-v2)** | **3.5 GB** |
| _npx | 933 MB |
| _logs | 14 MB |

**→ npm cache. Safe to run `npm cache clean --force` to free space.**

---

### 8. **.cursor — 2.9 GB**
| Subfolder | Size |
|-----------|------|
| **extensions** | **2.8 GB** |
| chats | 66 MB |

---

### 9. **Downloads — 2.8 GB**
| Item | Size |
|------|------|
| Telegram Desktop | 881 MB |
| Social OS (cyber-hud) | 822 MB |
| 03_SYSTEM FILE_... (BIT) | 258 MB |
| zlibrary-setup-latest.dmg | 121 MB |
| Other files/folders | ~700 MB |

---

### 10. **Library/Caches — 2.8 GB**
| Subfolder | Size |
|-----------|------|
| com.todesktop (Cursor ShipIt) | 766 MB |
| net.whatsapp.WhatsApp | 690 MB |
| puccinialin/cargo | 324 MB |
| Adobe | 319 MB |
| com.apple.textunderstandingd | 300 MB |
| SiriTTS | 261 MB |
| GeoServices | 74 MB |
| Homebrew | 53 MB |
| Others | ~100 MB |

---

### 11. **Documents — 868 MB**
| Subfolder | Size |
|-----------|------|
| Backup_Luna | 693 MB |
| POLI | 571 MB |
| xcode-project | 94 MB |
| Others | ~50 MB |

---

### 12. **.rustup — 1.2 GB**
| Subfolder | Size |
|-----------|------|
| toolchains (1.94.0-aarch64-apple-darwin) | 1.2 GB |

---

### Other scanned locations (smaller)
| Location | Size |
|----------|------|
| .cargo (registry, src) | 313 MB |
| .lmstudio | 322 MB |
| .config (raycast, yarn) | 158 MB |
| .gradle | 143 MB |
| .venv (home) | 147 MB |
| Applications | 106 MB |
| Library/Developer | 17 MB |
| Library/Logs | 38 MB |
| Library/Mobile Documents | 0 |
| Desktop | 24 MB |
| Movies | 256 KB |
| Pictures | 16 KB |
| .docker (config only) | 21 MB |
| .ollama | 256 KB |

---

## Not fully scanned
- **Library/CloudStorage** — contains OneDrive; full scan timed out (likely large if synced locally).

---

## Summary by category

| Category | Approx. total | Main contributors |
|----------|----------------|-------------------|
| **Containers & VMs** | **~22 GB** | Docker 18 GB, WhatsApp (Containers+Group) ~4 GB |
| **App support & caches** | **~26 GB** | Cursor (App Support + Caches), Arc, caches |
| **Dev & package caches** | **~22 GB** | uv, Bun, npm, .cursor, .cache, Projects |
| **Projects** | **9.5 GB** | 4D, yoloe, RAPS-1, others |
| **Downloads/Documents** | **~3.7 GB** | Downloads, Documents |
| **Other** | **~2 GB** | rustup, cargo, config, gradle, etc. |

**Rough total from scanned paths: ~85 GB** (rest of disk is system, other users, or unscanned dirs).

---

## Safe ways to free space (no data loss)

1. **Docker:** `docker system prune -a` (removes unused images/containers; keep if you use them).
2. **npm:** `npm cache clean --force`.
3. **uv:** `uv cache clean`.
4. **Bun:** `bun pm cache rm`.
5. **Cursor:** Remove unused extensions; clear caches from Cursor settings if available.
6. **Downloads:** Delete installers/DMGs and old archives you don’t need.
7. **WhatsApp:** In WhatsApp, reduce or clear media storage (back up first if needed).

---

*Report generated by scanning with `dust`; no files were modified or deleted.*
