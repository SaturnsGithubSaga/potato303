"""
widgets.py — PotatoSynth Widget Render Library
===============================================
Each widget is a pure function that returns a list of strings (lines).
No Textual, no state, no threading — just text.

tui.py imports these and calls them inside Textual Static.update()
at its own 10Hz poll loop.

Grid contract (from widgets.txt):
  Cell unit : 10 chars wide × 4 chars high
  Grid      : 12 columns × 7 rows  (inside the content area)
  Display   : 128 × 37 total TTY characters
              Header: 3 lines
              Footer: 2 lines  (blank line + shortcut bar)
              Content: 32 lines  → 8 cell-rows … but we use 7 for safety

All functions follow the same signature:
    render_<WidgetName>(val: float, config: dict) -> list[str]

Where:
    val    = current parameter value, float 0.0–1.0
    config = dict with keys from tui_layout.yaml widget node
             guaranteed keys: 'label', 'cc'
             optional keys:   'userval', 'lines', 'preset_data'
"""

import textwrap


# ── Helpers ────────────────────────────────────────────────────────────────────

def _bar(val: float, width: int = 10) -> str:
    """Filled / empty block bar, exactly `width` characters."""
    filled = max(0, min(width, int(round(val * width))))
    return "█" * filled + "░" * (width - filled)


def _cc_str_short(cc: int) -> str:
    """CC prefix that stays within 5 chars: 'CC 74' or 'CC104'."""
    return f"CC {cc}" if cc < 100 else f"CC{cc}"


# ── Widget 1: SmallDial  (1 col × 1 row = 10×4) ───────────────────────────────

def render_SmallDial(val: float, config: dict) -> list[str]:
    """
    ┌─────────
    |{label}:
    |CC74[0.2]
    █░░░░░░░░░
    """
    label = config["label"][:7]
    cc    = config["cc"]
    v1    = f"{val:.1f}"

    # line 2: conditional CC formatting to stay within 10 chars
    if cc < 100:
        cc_line = f"|CC{cc}[{v1}]"
    else:
        cc_line = f"CC{cc}[{v1}]"

    return [
        f"┌─────────",
        f"|{label}: ",
        cc_line,
        _bar(val, 10),
    ]


# ── Widget 2: LargeKnob  (2 col × 2 row = 20×8) ──────────────────────────────

_KNOB_FRAMES = [
    # Frame 0 (0.0)
    [
        "|       o  o       |",
        "|    o        o    |",
        "|   o          o   |",
        "|   o          o   |",
        "|    o _      o    |",
    ],
    # Frame 1 (0.1)
    [
        "|       o  o       |",
        "|    o        o    |",
        "|   o          o   |",
        "|   o          o   |",
        "|    -        o    |",
    ],
    # Frame 2 (0.2)
    [
        "|        o  o       |",
        "|     o        o    |",
        "|    o          o   |",
        "|    -          o   |",
        "|     o        o    |",
    ],
    # Frame 3 (0.3)
    [
        "|       o  o       |",
        "|    o        o    |",
        "|   -          o   |",
        "|   o          o   |",
        "|    o        o    |",
    ],
    # Frame 4 (0.4)
    [
        "|       o  o       |",
        "|     \       o    |",
        "|   o          o   |",
        "|   o          o   |",
        "|    o        o    |",
    ],
    # Frame 5 (0.5)
    [
        "|       |  o       |",
        "|    o        o    |",
        "|   o          o   |",
        "|   o          o   |",
        "|    o        o    |",
    ],
    # Frame 6 (0.6)
    [
        "|       o  |       |",
        "|    o        o    |",
        "|   o          o   |",
        "|   o          o   |",
        "|    o        o    |",
    ],
    # Frame 7 (0.7)
    [
        "|       o  o       |",
        "|    o        /    |",
        "|   o          o   |",
        "|   o          o   |",
        "|    o        o    |",
    ],
    # Frame 8 (0.8)
    [
        "|       o  o       |",
        "|    o        o    |",
        "|   o          -   |",
        "|   o          o   |",
        "|    o        o    |",
    ],
    # Frame 9 (0.9)
    [
        "|       o  o       |",
        "|    o        o    |",
        "|   o          o   |",
        "|   o          -   |",
        "|    o        o    |",
    ],
    # Frame 10 (1.0)
    [
        "|       o  o       |",
        "|    o        o    |",
        "|   o          o   |",
        "|   o          o   |",
        "|    o         -   |",
    ],
]


def render_LargeKnob(val: float, config: dict) -> list[str]:
    """2×2 cell knob with rotation frames. Total 20×8 characters."""
    label = config["label"]
    cc    = config["cc"]
    index = int(round(val * (len(_KNOB_FRAMES) - 1)))
    frame = _KNOB_FRAMES[index]

    top    = f"|{label[:18]:^18}|"
    cc_row = f"|{f'CC {cc}':^18}|"
    lines  = [top, cc_row] + frame + [f"|{f'Value: {val:.1f}':^18}|"]
    return lines


# ── Widget 3: VerticalIndicator  (1 col × 2 row = 10×8) ──────────────────────

def render_VerticalIndicator(val: float, config: dict) -> list[str]:
    """
    ╒════════╕
    ╡{label} ╞
    ╡{cc_str}╞
    ╡{tr_str}╞
    ╡        ╞
    ╡  ({in})  ╞
    ╡        ╞
    ╘════════╛
    """
    label    = config["label"]
    cc       = config["cc"]
    userval  = config.get("userval", 64)

    current_int = int(val * 127)
    indicator   = "██" if current_int > userval else "--"

    lbl_row = f"╡{label[:8]:^8}╞"
    cc_row  = f"╡{(f' CC {cc}' if cc < 100 else f' CC{cc}'):^8}╞"
    tr_row  = f"╡{(f'trig> {userval}' if userval < 100 else f'trig>{userval}'):^8}╞"
    in_row  = f"╡  ({indicator})  ╞"

    return [
        "╒════════╕",
        lbl_row,
        cc_row,
        tr_row,
        "╡        ╞",
        in_row,
        "╡        ╞",
        "╘════════╛",
    ]


# ── Widget 4: HorizontalIndicator  (2 col × 1 row = 20×4) ────────────────────

def render_HorizontalIndicator(val: float, config: dict) -> list[str]:
    """
    ╔══════════════════╗
    ╡{label}     ({in})╞
    ╡{tr_str}    ({in})╞
    ╚══════════════════╝
    """
    label   = config["label"][:10]
    userval = config.get("userval", 64)

    current_int = int(val * 127)
    indicator   = "████" if current_int > userval else "----"
    tr_str      = f"Trig>{userval}"[:10]

    row1 = f"╡{label:<10}  ({indicator})╞"
    row2 = f"╡{tr_str:<10}  ({indicator})╞"

    return [
        "╔══════════════════╗",
        row1,
        row2,
        "╚══════════════════╝",
    ]


# ── Widget 5: PresetBoxSquare  (2 col × 2 row = 20×8) ────────────────────────

def render_PresetBoxSquare(val: float, config: dict) -> list[str]:
    """Looks up the closest preset entry and renders a 20×8 box."""
    label       = config["label"][:18]
    cc          = config["cc"]
    preset_data = config.get("preset_data", [])

    lookup = _closest_preset(val, preset_data)
    cc_str = f"CC{cc:<3}"
    cc_val = lookup.get("trigger_cc", "?")
    wrapped = textwrap.wrap(lookup.get("name", ""), width=18)
    while len(wrapped) < 3:
        wrapped.append("")

    return [
        "╔══════════════════╗",
        f"║{label:<18}║",
        f"║{f'{cc_str}:{cc_val}':<18}║",
        "║░░░░░░░░░░░░░░░░░░║",
        f"║{wrapped[0]:<18}║",
        f"║{wrapped[1]:<18}║",
        f"║{wrapped[2]:<18}║",
        "╚══════════════════╝",
    ]


# ── Widget 6: PresetBoxLarge  (4 col × 2 row = 40×8) ─────────────────────────

def render_PresetBoxLarge(val: float, config: dict) -> list[str]:
    """40×8 variant of PresetBoxSquare."""
    label       = config["label"][:38]
    cc          = config["cc"]
    preset_data = config.get("preset_data", [])

    lookup = _closest_preset(val, preset_data)
    cc_str = f"CC{cc:<3}"
    cc_val = lookup.get("trigger_cc", "?")
    wrapped = textwrap.wrap(lookup.get("name", ""), width=38)
    while len(wrapped) < 3:
        wrapped.append("")

    return [
        "╔══════════════════════════════════════╗",
        f"║{label:<38}║",
        f"║{f'{cc_str}:{cc_val}':<38}║",
        "║░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║",
        f"║{wrapped[0]:<38}║",
        f"║{wrapped[1]:<38}║",
        f"║{wrapped[2]:<38}║",
        "╚══════════════════════════════════════╝",
    ]


def _closest_preset(val: float, preset_data: list) -> dict:
    """Return the preset entry whose 'float' key is closest to val."""
    if not preset_data:
        return {"name": "---", "trigger_cc": 0}
    return min(preset_data, key=lambda p: abs(p.get("float", 0) - val))


# ── Widget 7: OnOffIndicator  (2 col × 1 row = 20×4) ─────────────────────────

def render_OnOffIndicator(val: float, config: dict) -> list[str]:
    """
    ╔══════════════════╗
    ║{label}           ║
    ║{cc_str}  {c_str} ║
    ╚══════════════════╝
    """
    label   = config["label"][:18]
    cc      = config["cc"]
    userval = config.get("userval", 64)

    current_int = int(val * 127)
    cc_str = f"CC {cc}" if cc < 100 else f"CC{cc}"   # 5 chars
    c_str  = f"{'on|██':>11}" if current_int > userval else f"{'░░|off':>11}"

    row2 = f"║{cc_str}{c_str}  ║"

    return [
        "╔══════════════════╗",
        f"║{label:<18}║",
        row2,
        "╚══════════════════╝",
    ]


# ── Widget 8: MarkupBoxSmall  (2 col × 2 row = 20×8) ─────────────────────────

def render_MarkupBoxSmall(val: float, config: dict) -> list[str]:
    """Static text box. `val` is unused. config must have 'lines' dict."""
    lines_cfg = config.get("lines", {})
    rows = []
    for i in range(1, 7):
        text = str(lines_cfg.get(f"line{i}", ""))[:18]
        rows.append(f"║{text:<18}║")

    return [
        "╔══════════════════╗",
        *rows,
        "╚══════════════════╝",
    ]


# ── Widget 9: MarkupBoxLarge  (4 col × 2 row = 40×8) ─────────────────────────

def render_MarkupBoxLarge(val: float, config: dict) -> list[str]:
    """Static text box, wide variant. config must have 'lines' dict."""
    lines_cfg = config.get("lines", {})
    rows = []
    for i in range(1, 7):
        text = str(lines_cfg.get(f"line{i}", ""))[:38]
        rows.append(f"║{text:<38}║")

    return [
        "╔══════════════════════════════════════╗",
        *rows,
        "╚══════════════════════════════════════╝",
    ]


# ── Dispatch table ─────────────────────────────────────────────────────────────
# tui.py uses this instead of a big if/elif chain.

WIDGET_RENDERERS: dict[str, callable] = {
    "SmallDial":             render_SmallDial,
    "LargeKnob":             render_LargeKnob,
    "VerticalIndicator":     render_VerticalIndicator,
    "HorizontalIndicator":   render_HorizontalIndicator,
    "PresetBoxSquare":       render_PresetBoxSquare,
    "PresetBoxLarge":        render_PresetBoxLarge,
    "OnOffIndicator":        render_OnOffIndicator,
    "MarkupBoxSmall":        render_MarkupBoxSmall,
    "MarkupBoxLarge":        render_MarkupBoxLarge,
}
