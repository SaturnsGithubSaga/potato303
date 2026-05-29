# potato303

A headless LV2 synth engine running on a Raspberry Pi 3B. MIDI in, audio out, no display required.

Runs a [Midilab JC-303](https://github.com/midilab/jc303) acid bass synth controlled by a USB MIDI hardware controller. The Pi has no X server — everything lives in a TTY over SSH.

This is a port of [potatosynth](https://github.com/SaturnsGithubSaga/potatosynth) (originally for a Packard Bell netbook, Intel Atom N270, 32-bit antiX) to a Raspberry Pi 3B running **64-bit Raspberry Pi OS Lite (Trixie)**. The move to 64-bit was the critical step — see [Session Summaries](SESSION_SUMMARIES.md) for the full story.

---

## The Key Insight (jalv patch — read this first)

> **Version note:** This patch targets **jalv 1.6.8**. **jalv 1.8.0+ does not need it** — the upstream changelog lists "Add support for advanced parameters in console frontend" which is the same fix. Use 1.8.0 if your distro ships it.

Stock jalv 1.6.8 cannot set parameters on JUCE-style LV2 plugins via its console interface. JUCE exposes parameters as `patch:writable` Atom properties, not `lv2:ControlPort` inputs. The `jalv_process_command()` function only searches `jalv->ports` (ControlPorts) — it never reaches `jalv->controls`, where the Atom parameters live.

**The fix is two lines in `jalv_console.c`:**

```c
// jalv-1.6.8/src/jalv_console.c  (~lines 244-261)
// After the port search fails, fall through to patch:writable controls:

ControlID* control = NULL;
for (size_t i = 0; i < jalv->controls.n_controls; ++i) {
    ControlID* c = jalv->controls.controls[i];
    if (c->is_writable &&
        !strcmp(lilv_node_as_string(c->symbol), sym)) {
        control = c;
        break;
    }
}
if (control) {
    jalv->has_ui = true;   // ← critical: without this, jalv_apply_ui_events()
                           //     returns immediately every audio cycle and
                           //     silently discards all queued atoms
    jalv_set_control(jalv, control, sizeof(float), jalv->forge.Float, &value);
    fprintf(stderr, "%s = %f\n", sym, value);
}
```

The patched source is in `jalv-1.6.8/`. Build with:

```bash
cd jalv-1.6.8
meson setup build --buildtype=release
ninja -C build
sudo ninja -C build install
```

Once patched, you can type `JC303_cutoff = 0.75` at the jalv prompt and hear the filter move.

> **Why `jalv->has_ui = true`?** The atom queuing path in jalv is gated on whether a UI is attached. Without a UI, `jalv_apply_ui_events()` is a no-op. Setting `has_ui = true` tricks the audio thread into flushing the atom queue on every cycle, delivering the value change to the plugin.

---

## Setup (fresh Pi)

One script does everything — swap, packages, jalv (needs patch, see above), JC303 build, install:

```bash
# On your Mac/PC:
scp potato303_bootstrap.sh potato303:~/
ssh potato303 "bash ~/potato303_bootstrap.sh 2>&1 | tee ~/setup_log.txt"
```

Runtime: **~90 minutes** (dominated by JUCE compilation).

The script handles:
1. 2GB swap via `dphys-swapfile` (needed during build, idle at runtime)
2. All JUCE + audio apt deps
3. `git clone midilab/jc303` + submodules
4. Headless GUI stub (`src/gui/headless/`) to skip JUCE editor code
5. `cmake -DGUI=headless -march=native` + `make -j2`
6. `.lv2` bundle installed to `~/.lv2/`

> **Why 64-bit?** The 32-bit port failed in 5 sessions across multiple AI models.
> The root cause: `chowdsp_utils` (bundled in JC303) calls `xsimd::batch<double, neon>`
> which doesn't exist on ARMv7. On AArch64, `batch<double, neon64>` is fully supported.
> Zero source patches needed on 64-bit. See [SESSION_SUMMARIES.md](SESSION_SUMMARIES.md).

---

## What It Does

```
Hardware MIDI controller
        │  (USB → CH345 cable)
        ▼
   ALSA MIDI input
        │
   a2jmidid -e        (ALSA→JACK bridge)
        │
        ▼
   engine.py          (Python, mido)
        │
        ├── channel filter (midi_channel from mapping.yaml)
        │
        ├── note_on / note_off
        │       └── mido virtual output (PotatoSynth)
        │               └── jack_connect → JC303:in
        │
        └── control_change (CC)
                └── tmux send-keys → jalv stdin
                        └── "JC303_cutoff = 0.750\n"
                                └── patched jalv → patch:Set atom → plugin

   jalv (in tmux session "jalv")
        └── JC303 LV2 plugin
                ├── JC303:audio_out_1 → system:playback_1
                └── JC303:audio_out_2 → system:playback_2

   tui.py             (optional, passive display)
        └── reads /dev/shm/synth_state.json at 10 Hz
```

`engine.py` is the only process that writes to jalv. `tui.py` is a read-only Textual dashboard — killing it has no effect on audio.

---

## Prerequisites

**System packages** (installed automatically by `potato303_bootstrap.sh`):

```bash
sudo apt install build-essential cmake git jackd2 a2jmidid tmux \
                 libasound2-dev libjack-jackd2-dev python3-pip
```

**Python:**

```bash
pip3 install mido python-rtmidi pyyaml textual
```

**JACK realtime priority** (add to `/etc/security/limits.d/audio.conf`):

```
@audio  -  rtprio  99
@audio  -  memlock unlimited
```

---

## Configuration

Everything is driven from `config/JC303/mapping.yaml`:

```yaml
synth_profile:
  name: "JC-303 Acid Engine"
  lv2_uri: "http://github.com/midilab/JC303"

io:
  tracker_input_port: "CH345"   # substring match against mido port names
  midi_channel: 1               # 1–16; only this channel passes through

parameters:
  cutoff:
    cc: 74
    port_symbol: "JC303_cutoff"
    name: "Cutoff"
    default: 0.0
  # ... etc
```

`port_symbol` is the exact string you type at the jalv prompt. Find all available symbols by typing `controls` at the jalv interactive prompt after loading the plugin.

To adapt for a different LV2 plugin:
1. Run `jalv <plugin_uri>` and type `controls` to list all settable symbols.
2. Create `config/<PluginName>/mapping.yaml` with your CC→symbol assignments.
3. Update `MAPPING_FILE` in `engine.py`.

---

## Boot Sequence

```bash
chmod +x SYSTEM_BOOT.sh
./SYSTEM_BOOT.sh
```

Internally:

```
1. Kill existing jackd / jalv / a2jmidid / python3 / tmux
2. Start jackd: 44.1 kHz, 256-frame buffer, 2 periods, ALSA-MIDI bridge (-X seq)
3. sleep 3
4. Start a2jmidid -e  (exposes ALSA MIDI ports as JACK ports)
5. sleep 2
6. Start jalv inside detached tmux session "jalv"
7. sleep 2
8. jack_connect JC303:audio_out_1/2 → system:playback_1/2
9. Start engine.py in background
10. sleep 1
11. exec python3 tui.py  (foreground — kills on Ctrl+C, audio continues)
```

MIDI wiring is intentionally **not** done at boot. `engine.py` opens a virtual MIDI port (`PotatoSynth`), waits for `a2jmidid` to bridge it into JACK, then calls `jack_connect` at runtime. This enforces channel filtering before any MIDI reaches jalv.

---

## Runtime

Once booted the system is self-contained:

- **TUI** (`tui.py`): Reads `/dev/shm/synth_state.json` at 10 Hz. Safe to kill and restart.
- **Engine log**: `tail -f /dev/shm/engine.log`
- **jalv console**: `tmux attach -t jalv` — patched prompt always accessible.
- **Audio continues** as long as jackd + jalv are running. Losing SSH or killing the TUI has no effect.

---

## File Map

```
.
├── README.md                   This file
├── SESSION_SUMMARIES.md        Full port history and troubleshooting log
├── potato303_bootstrap.sh      One-shot Pi setup + JC303 build script
├── SYSTEM_BOOT.sh              Full boot script (JACK → jalv → engine → tui)
├── engine.py                   MIDI router + state writer (main process)
├── router.py                   Earlier, simpler router (reference)
├── tui.py                      Textual TUI dashboard (passive display)
├── widgets.py                  Render functions for TUI widgets
├── test_midi.py                MIDI diagnostics
├── sync.sh                     Sync helper
├── jalv-1.6.8/                 Patched jalv source (patch is the critical part)
│   └── src/
│       └── jalv_console.c      ← patch is here
└── config/
    └── JC303/
        ├── mapping.yaml        CC→symbol map, MIDI channel, defaults
        └── tui_layout.yaml     Widget grid layout for tui.py
```

---

## Why `tmux send-keys` and Not stdin Injection?

Writing to jalv's stdin via `/proc/<pid>/fd/0` goes to the terminal buffer, not jalv's `fgets()` read loop. `tmux send-keys` inputs directly into the tmux pane's pseudoterminal, which is what jalv's blocking `fgets` actually reads. The tmux session is a required part of the architecture, not a convenience.

---

## Hardware

| Component | Detail |
|---|---|
| Machine | Raspberry Pi 3B v1.2 |
| CPU | Broadcom BCM2837 Cortex-A53 @ 1.2 GHz (AArch64, NEON64) |
| RAM | 1 GB + 2 GB swap (dphys-swapfile) |
| OS | Raspberry Pi OS Lite **64-bit** (Trixie) |
| GCC | 14.2.0 |
| Audio | USB audio adapter (Pi 3B PWM jack is noisy) |
| MIDI | CH345 USB-to-MIDI cable |
| Controller | Polyend Tracker (used as hardware MIDI sequencer) |

> **Original hardware:** Intel Atom N270 netbook (32-bit, antiX 23) →
> see [potatosynth](https://github.com/SaturnsGithubSaga/potatosynth)
