#!/usr/bin/env python3
"""
tui.py — PotatoSynth TUI Dashboard
=====================================
Strictly passive: reads /dev/shm/synth_state.json written by engine.py.
No MIDI.  No subprocess calls.  No shared state with the audio path.

Resolves widget labels and CC numbers from:
  config/JC303/mapping.yaml  →  parameters.<slug>.name / .cc

Boot order:
  ./SYSTEM_BOOT.sh
  python3 engine.py   &    ← audio/MIDI critical path, never touch
  python3 tui.py           ← display only, safe to kill/restart

Keybindings (F-keys only):
  F2   Save state    (Phase 5 — stubbed)
  F5   Load state    (Phase 5 — stubbed)
  F9   Reload synth  (Phase 5 — stubbed)
  F10  Synth menu    (Phase 6 — stubbed)
  F11  Shutdown
  F12  Quit
"""

import json
import os
import yaml

from textual.app     import App, ComposeResult
from textual.widgets import Static
from textual.binding import Binding
from textual.timer   import Timer

from widgets import WIDGET_RENDERERS


# ── Paths ──────────────────────────────────────────────────────────────────────
LAYOUT_FILE  = "config/JC303/tui_layout.yaml"


# ── Loaders ────────────────────────────────────────────────────────────────────

def load_layout() -> dict:
    with open(LAYOUT_FILE, "r") as f:
        return yaml.safe_load(f)


def load_mapping(path: str) -> dict:
    """Load mapping.yaml and return the full dict."""
    with open(path, "r") as f:
        return yaml.safe_load(f)


def build_param_index(mapping: dict) -> dict:
    """
    Returns { slug: { 'label': str, 'cc': int, 'symbol': str } }
    from mapping.yaml parameters block.
    """
    index = {}
    for slug, param in mapping.get("parameters", {}).items():
        index[slug] = {
            "label":  param.get("name", slug),
            "cc":     int(param.get("cc", 0)),
            "symbol": param.get("port_symbol", slug),
        }
    return index


def load_preset_file(path: str, key: str) -> list:
    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        return data.get(key, [])
    except Exception as e:
        print(f"[tui] WARNING: could not load preset file {path}: {e}")
        return []


def read_state(state_file: str) -> dict:
    """Read synth_state.json. Returns {} on any read/parse error."""
    try:
        with open(state_file, "r") as f:
            return json.load(f)
    except Exception:
        return {}


# ── CSS builder ────────────────────────────────────────────────────────────────

def build_css(theme: dict, grid_cols: int, grid_rows: int) -> str:
    screen_bg = theme.get("screen_bg", "#000000")
    groups    = theme.get("groups", {})

    parts = [f"""
Screen {{
    layout: grid;
    grid-size: {grid_cols} {grid_rows};
    grid-gutter: 0 0;
    background: {screen_bg};
    padding: 0;
    min-width: 128;
    min-height: 37;
}}

#header {{
    column-span: {grid_cols};
    color: #c0c0c0;
    background: {screen_bg};
    padding: 0 1;
}}

#footer_bar {{
    column-span: {grid_cols};
    color: #606060;
    background: #0a0a0a;
    padding: 0;
}}
"""]

    for group_name, colors in groups.items():
        # border_c = colors.get("border_color", "#404040")
        bg_c     = colors.get("bg_color",     "#1a1a1a")
        value_c  = colors.get("value_color",  "#ffffff")
        parts.append(f"""
.{group_name} {{
    border: none;
    background: {bg_c};
    color: {value_c};
    padding: 0;
}}
""")
    return "\n".join(parts)


# ── Widget cell ────────────────────────────────────────────────────────────────

class WidgetCell(Static):
    """
    One grid cell.  Stores resolved render config; redraws on value change.
    render_cfg is built once at boot from mapping.yaml + layout node.
    """

    def __init__(self, render_cfg: dict, **kwargs):
        super().__init__(**kwargs)
        self.render_cfg = render_cfg
        self._val       = 0.0

    def on_mount(self) -> None:
        self._redraw()

    def update_val(self, new_val: float) -> None:
        if new_val != self._val:
            self._val = new_val
            self._redraw()

    def _redraw(self) -> None:
        widget_type = self.render_cfg.get("type", "SmallDial")
        renderer    = WIDGET_RENDERERS.get(widget_type)
        if renderer is None:
            self.update(f"ERR\n{widget_type}\nnot found")
            return
        lines = renderer(self._val, self.render_cfg)
        self.update("\n".join(lines))


# ── Header / footer ────────────────────────────────────────────────────────────

class HeaderBar(Static):
    def __init__(self, hcfg: dict, **kwargs):
        super().__init__(**kwargs)
        l1 = hcfg.get("line1", "POTATOSYNTH-OS")
        l2 = hcfg.get("line2", "")
        l3 = hcfg.get("line3", "")
        self._text = f"| {l1}\n╞═══ {l2}\n╘═════ {l3}"

    def on_mount(self) -> None:
        self.update(self._text)


class FooterBar(Static):
    def __init__(self, shortcuts: list, **kwargs):
        super().__init__(**kwargs)
        
        # Fallback if tui_layout.yaml lacks the shortcuts array
        if not shortcuts:
            shortcuts = [
                {"key": "F2",  "label": "Save state"},
                {"key": "F5",  "label": "Load state"},
                {"key": "F9",  "label": "Reload synth"},
                {"key": "F10", "label": "Synth menu"},
                {"key": "F11", "label": "Shutdown"},
                {"key": "F12", "label": "Quit"},
            ]

        # Split into two lines
        mid = len(shortcuts) // 2
        top_line = "   |   ".join(f"({s['key']}) {s['label']}" for s in shortcuts[:mid])
        bot_line = "   |   ".join(f"({s['key']}) {s['label']}" for s in shortcuts[mid:])

        # Center across 128 cols, add leading newline to center vertically in the cell
        self._default = f"\n{top_line:^128}\n{bot_line:^128}"

    def on_mount(self) -> None:
        self.update(self._default)

    def show_message(self, msg: str) -> None:
        self.update(f"\n\n{msg:^128}")

    def restore(self) -> None:
        self.update(self._default)

# ── App ────────────────────────────────────────────────────────────────────────

class PotatoSynthTUI(App):

    BINDINGS = [
        Binding("f2",  "save_state",   "Save state",   show=False),
        Binding("f5",  "load_state",   "Load state",   show=False),
        Binding("f9",  "reload_synth", "Reload synth", show=False),
        Binding("f10", "synth_menu",   "Synth menu",   show=False),
        Binding("f11", "shutdown",     "Shutdown",     show=False),
        Binding("f12", "quit",         "Quit",         show=False),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._layout     = load_layout()
        self._sys        = self._layout["system"]
        self._grid       = self._sys["grid"]
        self._state_file = self._sys.get("state_file", "/dev/shm/synth_state.json")
        self._poll_hz    = self._sys.get("poll_hz", 10)

        # Load mapping.yaml — single source of truth for labels + CCs
        mapping_path    = self._sys.get("mapping_file", "config/JC303/mapping.yaml")
        mapping         = load_mapping(mapping_path)
        self._param_idx = build_param_index(mapping)

        # Pre-load preset files (keyed by widget id)
        self._preset_cache: dict[str, list] = {}
        for node in self._layout.get("layout", []):
            if "preset_file" in node:
                self._preset_cache[node["id"]] = load_preset_file(
                    node["preset_file"],
                    node.get("preset_key", "")
                )

        # Build CSS from theme
        self.CSS = build_css(
            self._layout.get("theme", {}),
            self._grid["columns"],
            self._grid["rows"] + 2,   # +1 header row + 1 footer row
        )

        # Widget registry: symbol → WidgetCell  (for state updates)
        # A symbol can appear in multiple widgets (e.g. accent + accent_trig)
        self._symbol_cells: dict[str, list] = {}   # symbol → [WidgetCell, ...]
        self._all_cells: list[WidgetCell]   = []
        self._poll_timer: Timer | None      = None

    def _resolve_node(self, node: dict) -> dict:
        """
        Build the render_cfg dict a WidgetCell will use.
        Merges layout node + mapping.yaml param entry.
        Returns a self-contained config — no further YAML reads at runtime.
        """
        slug    = node.get("param", "")
        p_entry = self._param_idx.get(slug, {})

        cfg = {
            # from mapping.yaml (authoritative)
            "label":       p_entry.get("label", slug),
            "cc":          p_entry.get("cc", 0),
            "symbol":      p_entry.get("symbol", slug),
            # from layout node
            "type":        node.get("type", "SmallDial"),
            "userval":     node.get("userval", 64),
            "lines":       node.get("lines", {}),
            "preset_data": self._preset_cache.get(node.get("id", ""), []),
        }
        return cfg

    def compose(self) -> ComposeResult:
        # Header — spans full width, lives above the grid rows
        header = HeaderBar(self._sys.get("header", {}), id="header")
        header.styles.row        = 1
        header.styles.column     = 1
        header.styles.row_span   = 1
        header.styles.column_span = self._grid["columns"]
        yield header

        # Widget cells
        for node in self._layout.get("layout", []):
            wid      = node["id"]
            col      = node["col"]
            row      = node["row"]
            col_span = node.get("col_span", 1)
            row_span = node.get("row_span", 1)
            group    = node.get("theme_group", "global")

            render_cfg = self._resolve_node(node)
            cell = WidgetCell(render_cfg, id=wid, classes=group)

            # +1 to row because header occupies row 1
            cell.styles.column      = col
            cell.styles.row         = row + 1
            cell.styles.column_span = col_span
            cell.styles.row_span    = row_span

            # Register by symbol so _poll_state can find it fast
            symbol = render_cfg["symbol"]
            if symbol:
                self._symbol_cells.setdefault(symbol, []).append(cell)
            self._all_cells.append(cell)
            yield cell

        # Footer
        footer = FooterBar(
            self._sys.get("footer", {}).get("shortcuts", []),
            id="footer_bar"
        )
        footer.styles.row         = self._grid["rows"] + 2
        footer.styles.column      = 1
        footer.styles.column_span = self._grid["columns"]
        yield footer

    def on_mount(self) -> None:
        interval = 1.0 / self._poll_hz
        self._poll_timer = self.set_interval(interval, self._poll_state)

    def _poll_state(self) -> None:
        """Called at poll_hz. Reads state file, pushes changed values to cells."""
        state  = read_state(self._state_file)
        params = state.get("params", {})

        for symbol, cells in self._symbol_cells.items():
            new_val = params.get(symbol, 0.0)
            for cell in cells:
                cell.update_val(new_val)

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_save_state(self) -> None:
        self._flash("Save state — Phase 5 not yet implemented.")

    def action_load_state(self) -> None:
        self._flash("Load state — Phase 5 not yet implemented.")

    def action_reload_synth(self) -> None:
        self._flash("Reload synth — Phase 5 not yet implemented.")

    def action_synth_menu(self) -> None:
        self._flash("Synth menu — Phase 6 not yet implemented.")

    def action_shutdown(self) -> None:
        import subprocess
        self.exit()
        subprocess.run(["sudo", "poweroff"])

    def action_quit(self) -> None:
        self.exit()

    def _flash(self, msg: str) -> None:
        """Show a message in the footer for 3 seconds, then restore."""
        try:
            self.query_one("#footer_bar", FooterBar).show_message(msg)
            self.set_timer(3.0, lambda: self.query_one("#footer_bar", FooterBar).restore())
        except Exception:
            pass


if __name__ == "__main__":
    PotatoSynthTUI().run()
