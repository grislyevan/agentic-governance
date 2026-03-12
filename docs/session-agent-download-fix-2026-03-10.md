# Session: Agent Download Fix (2026-03-10)

## Objective

Fix the "Deploy Agent" download from the Detec server dashboard. Downloads were hanging indefinitely (button stuck on "Preparing..."), and the server installer finished with a warning on fresh installs.

## Root Causes Found

### 1. StreamingResponse line-by-line iteration (critical)

`api/routers/agent_download.py` returned the agent zip via `StreamingResponse(buf)` where `buf` is an `io.BytesIO`. Starlette iterates `BytesIO` by **lines** (splitting on `\n` bytes in binary data), dispatching each tiny chunk through a thread pool. For a 14 MB zip, this produced millions of thread-scheduled reads, capping throughput at ~100 KB/s even on localhost. The browser's `fetch()` + `res.blob()` call sat waiting for minutes, leaving the button stuck on "Preparing..." with no progress indication.

### 2. Missing Content-Length header

Because `StreamingResponse` uses `transfer-encoding: chunked`, browsers had no way to show download progress. Combined with the slow delivery, the download appeared completely stuck.

### 3. Installer health-check race (cosmetic)

The Inno Setup installer's post-install health check uses a 15-second timeout. On fresh installs, database migrations (4 Alembic steps) plus admin seeding can exceed this window, producing "Dashboard did not respond (15s). WARNING" even though the server starts successfully moments later.

## What Was Done

### Backend: Replace StreamingResponse with Response

Changed both download endpoints (`GET /agent/download` and `GET /agent/download/{token}`) from:

```python
return StreamingResponse(buf, media_type="application/zip", ...)
```

to:

```python
content = buf.getvalue()
return Response(
    content=content,
    media_type="application/zip",
    headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(len(content)),
    },
)
```

Since the zip is already fully assembled in memory, `Response` sends the full payload at once and includes `Content-Length` so browsers can show a progress bar.

**Result**: Download time dropped from 2+ minutes to under 1 second over the VM network. Throughput went from ~100 KB/s to 15.6 MB/s.

### Frontend: Button text clarity

Changed the download button label from `"Preparing..."` to `"Downloading…"` while the request is in flight.

**File**: `dashboard/src/pages/SettingsPage.jsx`

### Deployed to production VM

1. SCP'd fixed source files to `C:\Detec\src\` on the Windows VM (192.168.64.4)
2. Rebuilt `detec-server.exe` via PyInstaller
3. Stopped `DetecServer` Windows service, deployed new binary to `C:\Program Files\Detec\Server\`, restarted service
4. Verified download completes in <1 second from both localhost and the Mac host
5. Ran `git pull` on VM to keep source tree in sync
6. Rebuilt the full Inno Setup installer (`DetecServerSetup-0.1.0.exe`) with the fix baked in

### Files changed

| File | Change |
|------|--------|
| `api/routers/agent_download.py` | `StreamingResponse` -> `Response` with `Content-Length`; removed unused import |
| `dashboard/src/pages/SettingsPage.jsx` | Button text: "Preparing..." -> "Downloading..." |

## Commits

| Hash | Message |
|------|---------|
| `b523a4c` | fix: replace StreamingResponse with Response for agent downloads |

Pushed to `origin/main`.

## Server State After Session

- **DetecServer** Windows service: running, healthy (`/health` returns `{"status":"ok"}`)
- **Agent download**: working, fast (<1s for 14 MB zip)
- **Installer**: rebuilt at `C:\temp\installer-out\DetecServerSetup-0.1.0.exe` (37.3 MB)
- **Database**: SQLite at `C:\ProgramData\Detec\detec.db`, migrations current through `0004`
- **No DetecAgent service** running on the server (cleaned up in prior session)

## Context From Prior Session

This session continued work from an earlier session ([agent download debugging](845f2d94-6a50-449e-9185-f0ceed81cbdd)) that fixed:

- `ZIP_DEFLATED` re-compressing already-compressed installers (switched to `ZIP_STORED`)
- Stale `detec-agent/` directory in `dist/packages/`
- Misconfigured `DetecAgent` Windows service pointing to a dev build path
- Inno Setup `SaveStringsToFile` type mismatch (`TStrings` vs `TArrayOfString`)

The `StreamingResponse` issue was the final bottleneck preventing fast downloads.
