# Photo Addendum

Move-in / move-out condition photos and PDF reports for **Phillips Real Estate** and
**Bill & Red Property Management**. A web app installed to the iPhone/iPad Home Screen.

**Live app:** https://tvhoa93942.github.io/photo-addendum/
Install: open the link in Safari → Share → **Add to Home Screen**. Previous version (v3) stays at `/v3/`.

## Version 4.1 — save to the Photos app
- **📸 Save to Photos app**: copies of the photos go into the iPhone/iPad Photos app via the share sheet's
  **Save Images** (one tap — iOS doesn't let web apps write to Photos silently). Each copy carries EXIF
  date taken + time zone and a room/stage/address description, so Photos files it under the day it was taken.
- Offered automatically after Quick Shoot and when leaving an inspection (Settings → "Offer to save new photos
  to the Photos app"); also under the rooms, in ⋯ menus, and per photo in the viewer (or press-and-hold).
- Photos added from the library are never re-saved (they came from Photos). Saved photos are remembered
  (`p.album`); marking them is not an edit, so backup status doesn't change.

## What's in version 4
- **Every inspection is kept on the device** (a library) — reopen any property months later for move-out.
- **Saves instantly** after every photo and keystroke; ✓ Saved shows in the header. Saving stays
  instant even with hundreds of photos (each photo is stored once; only the small inspection record is re-saved).
- **Works offline** once opened online (service worker caches the app).
- **Quick Shoot** in-app rapid camera (room to room), plus the iPhone camera and photo library.
- Date, address and stage **stamped onto each photo**; library photos keep the date they were *taken* (EXIF).
- Photo viewer: double-tap zoom, swipe, caption, set main photo, delete with **Undo**.
- **Condition** (Good / Fair / Poor), one-tap comment phrases, move-in photos shown while shooting move-out.
- Move-out result (Normal wear / Cleaning / Damage) + estimated charges → **Deposit Deduction Worksheet**.
- Full-screen **signatures** for tenant and agent.
- PDF: summary page, photos grouped by room, after-repair photos with the room, worksheet, signatures,
  page X of Y, bookmarks, email-friendly size option.
- **iPad layout**: two-column library, move-out and move-in reference side by side, larger signature pad.
- Automatic, non-destructive upgrade of the inspection saved by v3 (the v3 save is left untouched).

## Where the data lives
On each device, in the app's own storage (IndexedDB `photo_addendum_v4`):
`inspections` (small JSON per inspection), `full` and `thumb` (JPEG bytes per photo, stored as ArrayBuffers),
`kv` (settings and UI state). Photo records note `src` (camera / quick / library / v3) and `album` (when saved to Photos). **iPhone and iPad keep separate copies** — move an inspection with
⋯ → Back up → AirDrop → ⋯ → Restore on the other device. Deleting the Home Screen icon erases its storage.
Backups are JSON Lines files (`{"format":"photo-addendum-backup"}` header, then inspection and photo lines);
Restore also accepts v1–v3 `.json` project files.

## Repository layout
| Path | What |
|---|---|
| `index.html`, `sw.js`, `manifest.webmanifest`, `icon-*.png` | The deployed site (built) |
| `src/app-template.html` | **Edit this** — the app without the jsPDF library (marker `/*__JSPDF_LIB__*/`) |
| `src/sw.js`, `src/manifest.webmanifest` | Service worker and web app manifest sources |
| `tools/build.sh` | Inlines jsPDF 2.5.1 and writes the deployable site (default: repo root) |
| `tools/make_icons.py` | Generates the app icons |
| `tests/` | Test suite (see below) |
| `v3/index.html` | Previous version, kept as a fallback |

## Build, test, deploy
```bash
bash tools/build.sh            # rebuild index.html, sw.js, manifest, icons in the repo root
bash tests/run_all.sh          # full test suite (WebKit + touch + stress); needs the setup in that file
```
When changing the app, bump `APP_VERSION` in `src/app-template.html` and `CACHE` in `src/sw.js`.
Deploy = commit and push to `main` (GitHub Pages serves the root). After a deploy, fully close and reopen
the Home Screen app; it picks up the new version as soon as it's online.

The tests drive the real UI in WebKit (Safari's engine, via WebKitGTK MiniBrowser) at iPhone and iPad sizes
with a mock camera: details entry, standard rooms, photos with EXIF dates and rotated portraits, viewer,
Quick Shoot, signatures, relaunch/resume, move-out, worksheet, all PDF types, backup/restore (copy and
replace), the v3 → v4 upgrade, the storage-lock regression, and opening with no network.
Things only a real iPhone can confirm: the native camera sheet, the share sheet, and Home Screen storage.
