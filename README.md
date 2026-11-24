<div align="center">

# DiskDiff

**A desktop tool for comparing two directory trees and syncing the differences.**

![Python](https://img.shields.io/badge/-Python-3776AB?logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/-Tkinter-3776AB)
![License](https://img.shields.io/badge/license-AGPLv3%20%2B%20Commercial-00D4C8.svg)

</div>

---

## What it does

DiskDiff is a single-file Tkinter desktop app for comparing two directory trees — e.g. a local disk against a backup, or two sync targets — and copying across whatever's missing. It's built for the "did my backup actually finish, and is anything different" question, without needing a full backup/sync suite.

## Features

- **Quick scan** — compares files by relative path + size
- **Deep scan** — additionally MD5-checksums files that match on size, to catch same-size-different-content cases
- **Duplicate finder** — finds duplicate files within the source tree (grouped by size, then MD5)
- Filterable diff tree: Missing / Extra / Mismatch / Unverified / Identical
- Copy missing files (or a selection) from source to destination
- Open any file's location in Explorer / Finder / file manager
- Case-insensitive path matching on Windows (NTFS is case-insensitive, and cloud-sync tools frequently re-case files on upload/download), overridable via `case_insensitive=False` on `compare_directories()`
- Unreadable files during a deep scan are reported as **Unverified**, not silently treated as identical

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.8+ |
| GUI | Tkinter (stdlib — no third-party packages required) |
| Hashing | MD5 (stdlib `hashlib`), for fast same-size-content verification |

## Screenshots

_Screenshots coming soon._

## Quick Start

```bash
git clone https://github.com/TheBooleanJulian/disk-diff
cd disk-diff
python disk_compare.py
```

No install step — `tkinter` ships with standard Python installs on Windows/macOS; on Linux install your distro's `python3-tk` package first.

1. Set **SOURCE** and **DESTINATION** folders.
2. Click **SCAN & COMPARE** for a fast size-based diff, or **DEEP SCAN (checksum)** to also verify content via MD5.
3. Use the filter panel to narrow the tree to one category.
4. Select rows and use the action panel to copy files to the destination or open them in the file explorer.

## How comparison works

- Files are matched between source and destination by relative path.
- **Quick scan** only compares file size — two files of the same size are reported as identical without reading their contents. Use **Deep scan** if you need content-level certainty.
- **Deep scan** MD5-checksums same-size files on both sides. If a file can't be read (permission error, locked file, I/O error, etc.), the pair is reported as **Unverified**, not identical — earlier versions of this tool silently treated unreadable files as matching, which could mask real differences.

## Known limitations

- Checksums are MD5 (fast, not cryptographically secure) — fine for detecting accidental differences, not for adversarial integrity checks.
- Symlinks are followed as regular files via `Path.rglob`; symlink loops are not detected.
- No cross-platform path-separator normalization is needed since scans always run on a single machine against local/mounted paths.

## Status / Roadmap

- [x] Quick scan (size-based) and deep scan (MD5 checksum)
- [x] Duplicate finder within the source tree
- [x] Filterable diff tree with copy and reveal-in-explorer actions
- [x] Case-insensitive matching for Windows/cloud-sync scenarios
- [x] Unverified-file reporting for unreadable files during deep scan
- [ ] Progress bar / cancel support for large trees
- [ ] Command-line mode for scripted/headless comparisons

## Changelog

- **2026-08-02** — Initial release: quick/deep scan, duplicate finder, filterable diff tree, copy and reveal-in-explorer actions, case-insensitive matching, unverified-file handling

## License

This project is dual licensed.

- Community Edition — [GNU Affero General Public License v3 (AGPLv3)](LICENSE). Free to use, modify, and self-host. If you distribute a modified version or run it as a network service, you must make the corresponding source available.
- Commercial License — for organisations that want to embed, modify, or distribute this software without AGPLv3's obligations. See [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).

---

<div align="center">
<sub>Built by <a href="https://github.com/TheBooleanJulian">@TheBooleanJulian</a></sub>
</div>
