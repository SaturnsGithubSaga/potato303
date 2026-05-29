#!/usr/bin/env python3
"""
engine.py — PotatoSynth Engine
================================
Reads:  config/JC303/mapping.yaml  (single source of truth)
Does:
  1. Build a CC→port_symbol dispatch table from mapping.yaml
  2. Listen for incoming MIDI CC on the configured port
  3. Inject parameter values into jalv via tmux send-keys
  4. Write current state to /dev/shm/synth_state.json at 10Hz
     (atomic rename — tui.py never reads a half-written file)

Boot order:
  ./SYSTEM_BOOT.sh
  python3 engine.py        ← replaces router.py
  python3 tui.py           ← optional, reads state passively

Exit: Ctrl+C  (safe — audio path is jalv/tmux, not this process)
"""

import json
import os
import mido          # type: ignore
import yaml          # type: ignore
import sys
import subprocess
import threading
import time

# ── Constants ──────────────────────────────────────────────────────────────────
TMUX_SESSION   = "jalv"
STATE_FILE     = "/dev/shm/synth_state.json"
STATE_TMP      = STATE_FILE + ".tmp"
STATE_WRITE_HZ = 10
MAPPING_FILE   = "config/JC303/mapping.yaml"


# ── Config ─────────────────────────────────────────────────────────────────────
def load_config() -> dict:
    try:
        with open(MAPPING_FILE, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[engine] ERROR: Could not load {MAPPING_FILE}: {e}")
        sys.exit(1)


def build_cc_table(config: dict) -> dict:
    """
    Returns { cc_number(int): { 'symbol': str, 'name': str } }
    Built from config['parameters'] which is keyed by friendly slug.
    """
    table = {}
    for _slug, param in config.get("parameters", {}).items():
        cc     = param.get("cc")
        symbol = param.get("port_symbol")
        name   = param.get("name", symbol)
        if cc is not None and symbol:
            table[int(cc)] = {"symbol": symbol, "name": name}
    return table


# ── MIDI port discovery ─────────────────────────────────────────────────────────
def find_port(keyword: str):
    for port in mido.get_input_names():
        if keyword.lower() in port.lower():
            return port
    return None


def find_jack_port(keyword: str) -> str | None:
    """Return the first JACK port name containing `keyword` (case-insensitive)."""
    try:
        result = subprocess.run(
            ["jack_lsp"], capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            if keyword.lower() in line.lower():
                return line.strip()
    except Exception as e:
        print(f"[engine] WARNING: jack_lsp failed: {e}")
    return None


def open_virtual_midi_out(port_name: str = "PotatoSynth", dest_jack_port: str = "JC303:in"):
    """
    Open a virtual mido output port, wait for a2jmidid to bridge it into JACK,
    then jack_connect it to `dest_jack_port`. Returns the open mido port object.
    """
    out = mido.open_output(port_name, virtual=True)
    print(f"[engine] Virtual MIDI output '{port_name}' opened — waiting for a2jmidid bridge...")
    time.sleep(1.5)  # give a2jmidid time to register the JACK port

    jack_src = find_jack_port(port_name)
    if jack_src:
        try:
            subprocess.run(
                ["jack_connect", jack_src, dest_jack_port],
                check=True, capture_output=True
            )
            print(f"[engine] JACK: {jack_src!r} → {dest_jack_port!r}")
        except subprocess.CalledProcessError as e:
            print(f"[engine] WARNING: jack_connect failed: {e.stderr.decode().strip()}")
    else:
        print(f"[engine] WARNING: Could not find JACK port for '{port_name}'. "
              f"Notes will NOT reach jalv.")
    return out


# ── jalv injection ─────────────────────────────────────────────────────────────
def send_to_jalv(cmd: str) -> None:
    subprocess.run(
        ["tmux", "send-keys", "-t", f"{TMUX_SESSION}:0", cmd, "Enter"],
        check=True
    )


# ── State writer thread ────────────────────────────────────────────────────────
class StateWriter(threading.Thread):
    """
    Daemon thread. Every 1/STATE_WRITE_HZ seconds it serialises `state`
    to STATE_FILE via atomic rename so tui.py never reads a torn file.
    """

    def __init__(self, state: dict, lock: threading.Lock):
        super().__init__(daemon=True)
        self.state = state
        self.lock  = lock
        self._stop = threading.Event()

    def run(self) -> None:
        interval = 1.0 / STATE_WRITE_HZ
        while not self._stop.is_set():
            t0 = time.monotonic()
            with self.lock:
                snapshot = {
                    "plugin": self.state["plugin"],
                    "params": dict(self.state["params"]),
                    "names":  dict(self.state["names"]),
                    "cc_map": dict(self.state["cc_map"]),
                    "ts":     self.state["ts"],
                }
            try:
                with open(STATE_TMP, "w") as f:
                    json.dump(snapshot, f)
                os.replace(STATE_TMP, STATE_FILE)
            except Exception as e:
                print(f"[engine] WARNING: state write failed: {e}")
            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, interval - elapsed))

    def stop(self) -> None:
        self._stop.set()


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    config   = load_config()
    cc_table = build_cc_table(config)
    io_cfg   = config.get("io", {})
    keyword  = io_cfg.get("tracker_input_port", "CH345")
    # midi_channel in config is 1-indexed (1-16); mido uses 0-indexed (0-15)
    midi_ch_cfg  = int(io_cfg.get("midi_channel", 1))
    midi_channel = max(0, min(15, midi_ch_cfg - 1))  # clamp & convert

    # Seed state — use defaults from mapping.yaml
    params = {}
    names  = {}
    for _slug, param in config.get("parameters", {}).items():
        symbol         = param.get("port_symbol", "")
        params[symbol] = float(param.get("default", 0.0))
        names[symbol]  = param.get("name", symbol)

    state = {
        "plugin": config.get("synth_profile", {}).get("name", "JC303"),
        "params": params,
        "names":  names,
        # symbol → cc so tui.py can show CC numbers without re-reading mapping
        "cc_map": {info["symbol"]: cc for cc, info in cc_table.items()},
        "ts":     time.time(),
    }
    lock = threading.Lock()

    # Guard: jalv tmux session must already exist
    result = subprocess.run(
        ["tmux", "has-session", "-t", TMUX_SESSION],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"[engine] ERROR: No tmux session '{TMUX_SESSION}' found.")
        print(f"  Start jalv first:  tmux new-session -d -s {TMUX_SESSION} "
              f"'~/jalv-1.6.8/build/jalv http://github.com/midilab/JC303'")
        sys.exit(1)

    in_port_name = find_port(keyword)
    if not in_port_name:
        print(f"[engine] ERROR: MIDI input port matching '{keyword}' not found.")
        print(f"  Available: {mido.get_input_names()}")
        sys.exit(1)

    writer = StateWriter(state, lock)
    writer.start()

    print(f"[engine] Mapping     : {MAPPING_FILE}")
    print(f"[engine] MIDI port   : {in_port_name}")
    print(f"[engine] MIDI channel: {midi_ch_cfg} (0-indexed: {midi_channel})")
    print(f"[engine] tmux target : {TMUX_SESSION}")
    print(f"[engine] State file  : {STATE_FILE}  (@{STATE_WRITE_HZ}Hz)")
    print(f"[engine] Routing {len(cc_table)} CCs → jalv.  Ctrl+C to stop.\n")

    midi_out = open_virtual_midi_out()

    try:
        with mido.open_input(in_port_name) as in_port:
            for msg in in_port:
                # ── Channel filter ─────────────────────────────────────────
                if getattr(msg, "channel", None) != midi_channel:
                    continue

                if msg.type in ("note_on", "note_off"):
                    midi_out.send(msg)

                elif msg.type == "control_change" and msg.control in cc_table:
                    entry  = cc_table[msg.control]
                    symbol = entry["symbol"]
                    val    = msg.value / 127.0
                    cmd    = f"{symbol} = {val:.3f}"
                    send_to_jalv(cmd)
                    with lock:
                        state["params"][symbol] = val
                        state["ts"] = time.time()
                    print(f"CC{msg.control:03d} → {cmd}")

    except KeyboardInterrupt:
        print("\n[engine] Stopped.")
    finally:
        writer.stop()
        midi_out.close()
        # Write a clean final snapshot before exit
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(state, f)
        except Exception:
            pass


if __name__ == "__main__":
    main()
