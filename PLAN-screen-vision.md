# Plan: "Let Claude see my screen" (read-only, permission-gated)

A design plan for adding screen-vision to the Desktop Domo app.

> **Status: implemented.** Build steps A–D are all done and verified
> (real non-black capture, consent dialog, vision reply, image stripping +
> downscale + hide-own-windows). New file `desktop_domo/screenshot.py`;
> touched `api.py`, `chat.py`, `config.py`, `history.py`, `main.py`.
>
> **One deviation from the design below:** on Linux the **portal** is not the
> primary engine. The `org.freedesktop.portal.Screenshot` D-Bus call succeeds,
> but its result vardict comes back as a `QDBusArgument` whose nested variant
> this PySide6 build can't demarshal (`asVariant()` returns `None`), so the
> saved file's URI is unreachable. **spectacle is the Linux engine** — present,
> reliable, equally read-only. The app's own preview + Send/Cancel dialog
> remains the universal permission gate on every OS.

## Goal

Let Claude look at my display(s) when useful, **as a static screenshot only**.
Claude never controls or changes anything, and I am **always asked before any
capture is sent**.

## Environment facts (checked on this machine)

- Desktop: **KDE Plasma on Wayland**, single display `eDP-1` (1920×1080).
- The app runs through **XWayland** (`QT_QPA_PLATFORM=xcb`). Consequence: a
  normal Qt `grabWindow` call returns a **black image** on Wayland — full-screen
  capture must go through the portal or a trusted KDE tool.
- Installed and usable: `spectacle` 6.7.3, `xdg-desktop-portal-kde` (the
  `kde.portal` backend), and `QtDBus` inside the project venv.

## Guiding principles

1. **Read-only by construction.** The feature only ever sends Claude a static
   screenshot via the vision API. No computer-use tool, no input injection, no
   ability to click/type/act — Claude receives a picture and nothing more. A
   line in the system prompt will state it can only look, not act.
2. **Nothing happens without an explicit action.** No background or automatic
   capture, ever.
3. **I see exactly what leaves my machine.** After capture, a preview dialog
   shows the actual image with **Send to Claude / Cancel**. The screenshot is
   transmitted only if I click Send. This is the core permission moment.
4. **Screenshots are never written to disk.** They stay in memory for the
   session; when history is saved to `history.json`, image data is replaced
   with a `[screenshot]` placeholder, so the transcript file never contains
   screen contents.

## User flow

1. A small **📷 "Show Claude my screen"** button appears in the chat header
   (next to the expand button).
2. Click it → the bubble/chat briefly hide (so they aren't in the shot) → the
   screen is captured.
3. A **preview + confirm dialog** opens: the screenshot thumbnail, an optional
   text box ("Ask about this screenshot…"), and **Send / Cancel**.
4. On **Send**, the image + question go to Claude as one message and the reply
   appears in the transcript. On **Cancel**, the image is discarded immediately.

## Cross-platform capture layer

Neither the portal nor spectacle exists on Windows, so capture is chosen
per-OS behind a single `capture_screen()` function.

| OS | Capture method | Extra dependency | OS permission prompt |
|----|----------------|------------------|----------------------|
| **Windows** | Qt `QScreen.grabWindow(0)` | none (in PySide6) | No → our preview dialog is the gate |
| **macOS** | Qt `QScreen.grabWindow(0)` | none | Yes (macOS "Screen Recording") |
| **Linux / KDE Wayland** | Portal via D-Bus (fallback: spectacle) | none (QtDBus + spectacle present) | Yes (KDE portal consent dialog) |

Dispatch:

```
if platform in ("win32", "darwin"):  → Qt grabWindow(0)       # zero deps, native
else (linux):                        → portal via D-Bus       # KDE/GNOME consent dialog
                                        └─ fallback: spectacle # if the portal call fails
```

- Qt's `grabWindow` is the easiest path for Windows: already part of PySide6,
  no new package, native full-screen capture (also works on macOS). It returns
  black on Wayland, which is why Linux uses the portal instead.
- **Decision:** portal is the primary Linux engine (its OS-enforced consent
  prompt matches the "always ask" requirement), with spectacle as an automatic
  fallback if the portal call fails.
- On **every** OS, the app's own preview + Send/Cancel dialog is the universal
  permission gate. macOS and Linux additionally get the OS's own prompt.

The app is Windows-ready by design with no extra dependencies; the Linux path
is what runs on the current Arch machine.

## Follow-up behaviour

**Decision: remember for the session.** A sent screenshot stays in the
in-memory conversation so follow-up questions work (e.g. "what's in the
top-left?"). It is never written to disk (stripped to a `[screenshot]`
placeholder on save). Trade-off: slightly higher per-message token cost while
the image remains in context.

## Technical pieces

- **New `desktop_domo/screenshot.py`** — the capture backend. Hides our
  windows, captures the display via the per-OS method above, returns PNG bytes.
- **`api.py`** — extend `reply()` to accept an optional image so message
  content becomes `[{image…}, {text…}]` (Opus 4.8 supports vision). Downscale
  to ~1568px on the long edge before sending to keep token cost modest.
- **`chat.py`** — the 📷 button, the preview/consent dialog, hide-then-restore
  windows during capture, and stripping image bytes out of history before
  `history.save()`.
- **`config.py`** — knobs: downscale target, capture engine override.

## Build order (small, verifiable steps)

- **A.** Capture backend alone — prove a real, non-black screenshot of the
  desktop saves to a file under Wayland.
- **B.** The preview + Send/Cancel consent dialog.
- **C.** Vision wired into `api.py`; a captured + approved image gets a reply.
- **D.** Privacy polish: strip images from saved history, downscale, hide own
  windows during capture.

## Cost & privacy notes

- Screenshots can contain anything on screen; the Send button is the gate and
  the preview lets me catch sensitive content before it leaves the machine.
- Sent images are billed as input tokens; the ~1568px downscale keeps a 1080p
  capture reasonably cheap.

## Chat Resume Code

- claude --resume f30f87dc-3ddd-42ee-a481-21df98699363