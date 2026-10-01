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
# NK57 Monospace (normal width), loaded from the project's Fonts/ folder by
# load_fonts() (Qt) and font_face_css() (the transcript page). The few
# symbols it lacks (✕ ✎) fall through to Tahoma, then Verdana / Segoe UI /
# sans-serif — which is also the whole stack if the folder is missing.
# The folder also has Cd / Sc / Se / Ex (narrower to wider) cuts and
# Lt / Bk / Sb / Eb weights; swap the file names below to try them.
FONT_DIR = config.PROJECT_ROOT / "Fonts" / "nk57_monospace"
FONT_FAMILY = "NK57 Monospace"                 # the family name inside the files
FONT_FILES = {                                 # file -> (CSS weight, CSS style)
    "NK57 Monospace No Rg.otf": (400, "normal"),
    "NK57 Monospace No Rg It.otf": (400, "italic"),
    "NK57 Monospace No Bd.otf": (700, "normal"),
    "NK57 Monospace No Bd It.otf": (700, "italic"),
}
FONT_FAMILIES = [FONT_FAMILY, "Tahoma", "Verdana", "Segoe UI", "sans-serif"]
FONT_CSS = f'"{FONT_FAMILY}", Tahoma, Verdana, "Segoe UI", sans-serif'
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


def _font_paths():
    """The bundled font files that are actually present, with their CSS face."""
    for name, face in FONT_FILES.items():
        path = FONT_DIR / name
        if path.exists():
            yield path, face


def load_fonts():
    """Register the bundled font with Qt. Call once, after QApplication exists."""
    from PySide6.QtGui import QFontDatabase

    for path, _face in _font_paths():
        QFontDatabase.addApplicationFont(str(path))


def font_face_css():
    """@font-face rules for the transcript page.

    The web view doesn't see fonts registered with Qt, so it loads the same
    files itself, straight off disk.
    """
    return "\n".join(
        f'@font-face {{ font-family: "{FONT_FAMILY}"; src: url("{path.as_uri()}");'
        f" font-weight: {weight}; font-style: {style}; }}"
        for path, (weight, style) in _font_paths()
    )


def app_font(px=TEXT_PX, italic=False):
    """The bundled mono face, falling back through FONT_FAMILIES per glyph."""
    from PySide6.QtGui import QFont

    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setStyleHint(QFont.SansSerif)
    font.setPixelSize(px)
    font.setItalic(italic)
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
