"""Colours, fonts and names shared by the chat window and its transcript.

The layout follows the retro-messenger design (clay title bar, rounded speech
bubbles, timestamp strip), but in Domo's dark brown instead of the original
cream so the app keeps its dark-mode feel. The clay accents are used as-is;
the light surfaces are swapped for dark stand-ins, noted against each one.

Both the Qt widgets (chat.py) and the transcript page (assets/transcript.html,
via ``css_variables()``) read from here, so a colour only changes in one place.
"""

from desktop_domo import config

# --- Clay accents (unchanged from the design) ------------------------------
CLAY = "#D97757"          # title bar, outgoing bubbles, Send, Domo's avatar
CLAY_DARK = "#B85C3E"     # borders on clay elements, Send pressed
CLAY_HOVER = "#C96A4B"    # Send hover
CLAY_LIGHT = "#E38B6D"    # title bar button hover ("slightly lighter clay")
CREAM = "#FAF9F5"         # text on clay
ONLINE_GREEN = "#788C5D"  # status dot
DANGER = "#A12626"        # hover on ✕, which quits the whole app

# --- Dark-mode surfaces (the design's light colours, re-mapped) -----------
BACKGROUND = "#371B11"    # design: cream      — window + message area
SURFACE = "#2A140C"       # design: cream-dark — timestamp strip, input bar
BUBBLE_IN = "#4E2A1D"     # design: bubble-gray — incoming bubbles
INK = "#F0EEE6"           # design: ink        — text on incoming bubbles
MUTED = "#A8968D"         # design: muted      — timestamps, hints, typing line
BORDER = "#5C3424"        # design: border     — window border, input bar top
DIVIDER = "#4A2619"       # design: divider    — line under the timestamp strip
SCROLL_HANDLE = "#5C3424"
SCROLL_HANDLE_HOVER = "#7A4A36"

# --- Text field (stays light, as it was before the redesign) --------------
FIELD = "#F9EFEB"
FIELD_TEXT = "#141413"
FIELD_BORDER = "#B0AEA5"
PLACEHOLDER = "#888780"

# --- Type ------------------------------------------------------------------
# Tahoma first for the retro look; Verdana / Segoe UI / sans-serif keep it a
# sans face on machines without it (most Linux installs).
FONT_FAMILIES = ["Tahoma", "Verdana", "Segoe UI", "sans-serif"]
FONT_CSS = 'Tahoma, Verdana, "Segoe UI", sans-serif'
TEXT_PX = 13              # messages, input, names
SMALL_PX = 11             # timestamps, status, hints, typing line

# --- Names -----------------------------------------------------------------
ASSISTANT_NAME = "Domo"
ASSISTANT_INITIAL = ASSISTANT_NAME[0]

# --- Domo's avatar beside each reply ----------------------------------------
# The bubble artwork, in a fixed box that keeps Helper.png's 474x296 shape, so
# it's the same size next to a one-word reply and a long one. If the PNG is
# missing, the clay square with ASSISTANT_INITIAL is drawn instead.
AVATAR_IMAGE = config.PROJECT_ROOT / "Helper.png"
AVATAR_W = 40
AVATAR_H = 25
# The same picture in the title bar, a touch bigger (same 474x296 shape).
TITLE_AVATAR_W = 42
TITLE_AVATAR_H = 26


def app_font(px=TEXT_PX):
    """Tahoma, falling back through FONT_FAMILIES, then any sans-serif face."""
    from PySide6.QtGui import QFont

    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setStyleHint(QFont.SansSerif)
    font.setPixelSize(px)
    return font


def css_variables():
    """The palette as a CSS ``:root`` block for the transcript page."""
    names = {
        "clay": CLAY,
        "cream": CREAM,
        "bg": BACKGROUND,
        "bubble-in": BUBBLE_IN,
        "ink": INK,
        "muted": MUTED,
        "scroll": SCROLL_HANDLE,
        "scroll-hover": SCROLL_HANDLE_HOVER,
        "text-px": f"{TEXT_PX}px",
        "small-px": f"{SMALL_PX}px",
        "avatar-w": f"{AVATAR_W}px",
        "avatar-h": f"{AVATAR_H}px",
    }
    body = " ".join(f"--{key}: {value};" for key, value in names.items())
    return f":root {{ {body} --font: {FONT_CSS}; }}"


def format_time(dt, now=None):
    """'9:41 AM' for today; 'Sep 30, 9:41 AM' for anything older.

    Built by hand because strftime's no-leading-zero flag (%-I) is
    platform-specific and fails on Windows.
    """
    clock = f"{dt.hour % 12 or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"
    if now is not None and dt.date() != now.date():
        return f"{dt.strftime('%b')} {dt.day}, {clock}"
    return clock
