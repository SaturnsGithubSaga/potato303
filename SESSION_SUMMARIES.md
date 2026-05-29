# 2026-25-05

### potatosynth — Pi Revival Session

_Raspberry Pi 3B v1.2 | Trixie | potato303@192.168.1.84_

---

## What we're building

Reviving [potatosynth](https://github.com/SaturnsGithubSaga/potatosynth) — a headless JACK-based LV2 synth host — on a Pi 3B, replacing the original Atom N270 netbook running antiX.

---

## Decisions made

|Topic|Decision|Reason|
|---|---|---|
|OS|Raspberry Pi OS Lite 32-bit (Trixie)|Better Pi 3B hardware support, richer apt ecosystem, lean enough|
|jalv|Build from source (1.6.8 from repo)|apt ships 1.6.8-1+b1, patch is already in the bundled source|
|JC-303|Build from source via `build_jc303.sh`|No prebuilt ARM LV2 available|
|Python/shell files|Copy as-is|Architecture-agnostic|
|Audio out|USB adapter recommended|Pi 3B PWM jack is noisy|

---

## Changes made to `build_jc303.sh`

**Build flags** — replace the i686 block with:

```bash
# 3. Configure CMake for ARMv7 (Pi 3B)
echo "Configuring CMake for ARMv7 (NEON)..."
export CFLAGS="-O3 -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -ffast-math"
export CXXFLAGS="-O3 -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -ffast-math"
export LDFLAGS="-latomic"
```

**Clone target** — `/tmp` is tmpfs (461MB, fills up fast), move to SD card:

```bash
# was: /tmp/jc303_src
# now: ~/jc303_src
```

Change every reference to `/tmp/jc303_src` → `~/jc303_src`.

**cmake flags** — added headless flag:

```bash
-DJUCE_HEADLESS_PLUGIN_CLIENT=1
```

---

## Packages installed

```bash
# Audio
sudo apt install alsa-utils jackd2 libasound2-dev libjack-jackd2-dev

# Build tools + JUCE deps
sudo apt install build-essential cmake pkg-config git \
  libfreetype6-dev libx11-dev libxcomposite-dev libxcursor-dev \
  libxext-dev libxinerama-dev libxrandr-dev libxrender-dev \
  libfontconfig1-dev libcurl4-openssl-dev libgl-dev libgtk-3-dev

# ninja (the right one)
sudo apt install ninja-build
# note: 'ninja' (0.1.3) is a different, wrong package

# jalv deps for meson build
sudo apt install meson lv2-dev libserd-dev libsord-dev libsratom-dev liblilv-dev libreadline-dev
```

---

## jalv build

```bash
cd ~/potatosynth/jalv-1.6.8
meson setup build
ninja -C build
sudo /usr/bin/ninja -C build install
```

Note: use full path `/usr/bin/ninja` for sudo — restricted PATH issue.

---

## Pitfalls hit

- `ninja` package (0.1.3) is not ninja-build — install `ninja-build`
- After removing wrong `ninja`, run `hash -r` to clear bash's command cache
- `/tmp` is tmpfs, only ~461MB — JC-303 clone + build artifacts overflow it
- `libwebkit2gtk-4.0-dev` doesn't exist on Trixie, it's `libwebkit2gtk-4.1-dev`
- swapfile added: `sudo fallocate -l 2G /swapfile` (OOM killer was striking during JUCE compile)

---

## Current status

⏳ `build_jc303.sh` compiling with corrected flags + `~/jc303_src` target

---

## Still to do

- [ ] Verify JC-303 `.lv2` lands in correct path
- [ ] jalv smoke test: `jalv <jc303.lv2>`
- [ ] Port/verify `engine.py`, `SYSTEM_BOOT.sh`, `mapping.yaml`, `tui.py`
- [ ] JACK autostart on boot
- [ ] MIDI routing (`a2jmidid`)
- [ ] Test full chain end to end

---

_Claude Sonnet 4.6 — claude.ai_

# 2026-26-05

### potatosynth — Pi Revival Session 2

_Raspberry Pi 3B v1.2 | Trixie | potato303@192.168.1.84_

---

## Context

Continuation of Session 1. JC-303 still not compiling. jalv is built and installed.

---

## Root cause identified

The bundled xsimd in chowdsp_utils is **version 10.0.0rc0** — a release candidate with a known NEON/GCC14 template recursion bug in `xsimd_neon.hpp`. This causes a hard compile error in `chowdsp_BBDFilterBank.h`, triggered via `src/gui/amadeusp/Gui.cpp`. The error presents as:

```
make[2]: *** [CMakeFiles/JC303.dir/build.make:349: CMakeFiles/JC303.dir/src/gui/amadeusp/Gui.cpp.o] Error 1
```

This is **not** a hardware limitation — Pi 3B is capable of running JC-303.

---

## Fix applied to `build_jc303.sh`

**Replace bundled xsimd 10.0.0rc0 with 11.1.0** after clone, before cmake:

```bash
git submodule update --init --recursive
cd "$WORK_DIR/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/"
rm -rf xsimd
git clone --branch 11.1.0 --depth 1 https://github.com/xtensor-stack/xsimd.git
cd "$WORK_DIR"
```

**Script also corrected** — had drifted back to old i686 flags and `/tmp` clone target. Canonical state of `build_jc303.sh` as of end of session:

- `WORK_DIR="$HOME/jc303_src"` (not `/tmp`)
- ARMv7 NEON flags (not i686/SSE3)
- Explicit `git submodule update --init --recursive` (not `--recursive` on clone, which was silently failing)
- xsimd swap block included
- `-DCMAKE_CXX_STANDARD=14`
- `-DJUCE_HEADLESS_PLUGIN_CLIENT=1`
- `-DJUCE_BUILD_EXTRAS=OFF`

---

## Swapfile

Added 2G swapfile (OOM killer was striking during JUCE compile). Does **not** survive reboot unless `/etc/fstab` is updated:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

Swapfile was lost on reboot during this session — confirm it's in `/etc/fstab` before next compile attempt.

---

## Pitfalls hit this session

- `--recursive` on `git clone` silently failing to populate submodules — fixed with explicit `git submodule update --init --recursive`
- Script kept drifting back to i686/`/tmp` state across token resets between Claude sessions
- `rm -rf "$WORK_DIR"` was commented out at one point to preserve manual xsimd swap — now unnecessary since the swap is in the script; must stay uncommented
- Swapfile not persisted across reboot — needs `/etc/fstab` entry

---

## Current status

⏳ `build_jc303.sh` ready to run with xsimd 11.1.0 patch + correct ARMv7 flags. Swapfile needs to be re-established before running.

---

## Still to do

- [ ] Confirm swapfile persists (`/etc/fstab` entry)
- [ ] Run `build_jc303.sh` and verify JC-303 `.lv2` lands in `~/.lv2/`
- [ ] jalv smoke test: `jalv http://github.com/midilab/JC303`
- [ ] Port/verify `engine.py`, `SYSTEM_BOOT.sh`, `mapping.yaml`, `tui.py`
- [ ] JACK autostart on boot
- [ ] MIDI routing (`a2jmidid`)
- [ ] Test full chain end to end

---

_Claude Sonnet 4.6 — claude.ai_

# 2026-26-05

### potatosynth — Pi Revival Session 3

_Raspberry Pi 3B v1.2 | Trixie | potato303@192.168.1.84_

---

## Context

Continuation of Sessions 1 & 2. jalv built and installed. JC-303 still not compiling despite xsimd swap fix from Session 2.

---

## What we found this session

**The xsimd path in `build_jc303.sh` is wrong.**

The script assumes:
```
lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd
```

But a fresh probe clone showed:
```
find lib -name "xsimd" -type d
→ (no output)
```

`lib/` does not exist after a bare `git clone` — submodules are not populated yet at that point. More importantly, after `git submodule update --init --recursive`, the actual path is almost certainly **not** `chowdsp_utils-src` — that suffix was assumed in a previous session and never verified. The `cd` in the xsimd swap block likely silently failed or landed in the wrong place, meaning **the xsimd swap never actually ran**, and the same GCC14/NEON bug from Session 2 kept hitting.

**The cross-compile attempt (Docker on home-assistant@192.168.1.60) was also abandoned** — JUCE insists on building `juceaide`, a native host tool, before cross-compiling the plugin. This requires the full GUI/graphics stack (freetype, harfbuzz, X11) on the host machine, which is not worth fighting. Native compile on the Pi is the right approach.

---

## First thing to do next session

Find the real xsimd path on a fresh clone. Run this on the Pi:

```bash
git clone https://github.com/midilab/jc303.git /tmp/jc303_probe
cd /tmp/jc303_probe
git submodule update --init --recursive
find . -name "xsimd" -type d
```

Paste the output. That gives us the real path to put in the xsimd swap block. Then update `build_jc303.sh` with the correct path and run it.

---

## Known good state of `build_jc303.sh` (minus the broken xsimd path)

- `WORK_DIR="$HOME/jc303_src"`
- `git submodule update --init --recursive` (separate from clone)
- ARMv7 flags: `-march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -ffast-math`
- `export LDFLAGS="-latomic"`
- `-DCMAKE_CXX_STANDARD=14`
- `-DJUCE_HEADLESS_PLUGIN_CLIENT=1`
- `-DJUCE_BUILD_EXTRAS=OFF`
- `make -j1` (single core, safe for 1GB RAM + 2G swap)
- xsimd swap target: **11.1.0** — path TBD from probe above

---

## Swapfile

Must be present before compiling. Verify with `swapon --show`. If missing:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## Still to do

- [ ] Find real xsimd path (probe command above)
- [ ] Fix xsimd path in `build_jc303.sh` and run it
- [ ] Verify JC-303 `.lv2` lands in `~/.lv2/`
- [ ] jalv smoke test: `jalv http://github.com/midilab/JC303`
- [ ] Port/verify `engine.py`, `SYSTEM_BOOT.sh`, `mapping.yaml`, `tui.py`
- [ ] JACK autostart on boot
- [ ] MIDI routing (`a2jmidid`)
- [ ] Test full chain end to end

---

_Claude Sonnet 4.6 — claude.ai_

Small note from me, the user: I created the swapfile and added it to fstab. I am now powering off the Pi, so we should check if the swapfile has persisted as well :)

# 2026-27-05

### potatosynth — Pi Revival Session 4

_Raspberry Pi 3B v1.2 | Trixie | potato303@192.168.1.84_

---

## Context

Continuation of Sessions 1–3. jalv built and installed. JC-303 still not compiling. This session was sparring/detective work — no agent, just analysis.

---

## What we figured out

**The xsimd diagnosis from Session 2 was wrong.** Through browsing the JC-303 repo, we found:

- xsimd is not a submodule of JC-303 at all
- chowdsp_utils is pulled via `FetchContent` at cmake configure time, pinned to commit `ffc70ba399f9afaeefb996eb14e55a1d487270b8`
- At that commit, chowdsp_utils has its own SIMD abstraction (`chowdsp_simd`) and does **not** bundle or fetch xsimd externally
- The xsimd swap path (`lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd`) never existed — the `cd` was silently failing or landing nowhere

**Root cause reframed:** The compile error is a GCC14 strictness issue in chowdsp's own SIMD headers, not an xsimd version problem. The old Atom N270 + antiX setup never hit this because antiX shipped GCC 11/12, which was more forgiving.

**Fix:** Use GCC 12 explicitly instead of the system default GCC 14.

---

## Changes made to `build_jc303.sh`

**Removed** the entire xsimd swap block:

```bash
# (deleted)
# Swap bundled xsimd 10.0.0rc0 (broken on GCC14/NEON) with 11.1.0
echo "Patching xsimd to 11.1.0..."
cd "$WORK_DIR/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/"
rm -rf xsimd
git clone --branch 11.1.0 --depth 1 https://github.com/xtensor-stack/xsimd.git
cd "$WORK_DIR"
```

**Added** two compiler flags to the cmake invocation:

```bash
-DCMAKE_C_COMPILER=gcc-12 \
-DCMAKE_CXX_COMPILER=g++-12 \
```

**Installed** gcc-12 and g++-12 on the Pi (`sudo apt install gcc-12 g++-12` — confirmed working).

**Swapfile** confirmed persisted across reboot (`swapon --show` shows `/swapfile 2G`).

---

## Current status

⏳ `build_jc303.sh` ran at end of session but produced errors — output too long to capture. **First thing next session: run it again and capture the errors.**

---

## Still to do

- [ ] Run `build_jc303.sh` and paste error output
- [ ] Verify JC-303 `.lv2` lands in `~/.lv2/`
- [ ] jalv smoke test: `jalv http://github.com/midilab/JC303`
- [ ] Port/verify `engine.py`, `SYSTEM_BOOT.sh`, `mapping.yaml`, `tui.py`
- [ ] JACK autostart on boot
- [ ] MIDI routing (`a2jmidid`)
- [ ] Test full chain end to end

---

_Claude Sonnet 4.6 — claude.ai_

**Here is your clean Session Summary 5:**

---

# 2026-28-05

### potatosynth — Pi Revival Session 5

_Raspberry Pi 3B v1.2 | Trixie | potato303@192.168.1.84_

---

## Context

Continuation of Sessions 1–4. Multiple attempts to compile JC-303 with GCC-12, relaxed flags, and the lighter `midilab` GUI.

---

## What happened this session

- Updated `build_jc303.sh` with improved CMake flags (`-DGUI=midilab`, relaxed compiler warnings, `-fpermissive`, template backtrace limit, etc.).
- Build progressed significantly further than previous attempts.
- Successfully compiled:
  - All Open303 DSP core
  - RTNeural + GuitarML models
  - BinaryData resources
  - JUCE infrastructure
  - `midilab` GUI resources

**Failed during final linking/compilation of `src/gui/midilab/Gui.cpp`**

### Root cause of failure

```bash
In file included from .../chowdsp_utils/.../xsimd/... 
error: too many initializers for 'xsimd::types::simd_register<double, xsimd::neon>'
error: static assertion failed: usage of batch type with unsupported type
```

The error is a **NEON / double-precision incompatibility** inside the bundled xsimd version used by `chowdsp_utils` when targeting ARMv7 with NEON.

Even though we switched to the `midilab` GUI (much lighter than AmadeusP), the underlying DSP code still pulls in chowdsp_utils → xsimd, which has ARMv7 + double precision issues under GCC 12.

---

## Current status

- Core DSP compiled successfully.
- GUI + final plugin binary failed due to xsimd NEON/double issue.
- No usable `JC303.lv2` bundle produced yet.

---

## Still to do (updated)

- [ ] Fix xsimd / chowdsp_utils NEON compatibility on ARMv7
- [ ] Consider forcing single-precision (`float`) everywhere or disabling problematic modules
- [ ] Try building with even stronger compiler restrictions or older xsimd
- [ ] Verify `jalv` smoke test once plugin is built
- [ ] Port/verify `engine.py`, `SYSTEM_BOOT.sh`, `mapping.yaml`, `tui.py`
- [ ] JACK autostart + MIDI routing (`a2jmidid`)
- [ ] Full end-to-end test

---

**Session Notes:**
The build is getting closer — we cleared the previous GUI-heavy AmadeusP roadblock by switching to `midilab`. Now the blocker is deep in the SIMD math library used by the GuitarML neural models. This is a classic ARMv7 + modern SIMD library pain point.

---

~~_Claude Sonnet 4.6 — claude.ai_~~ this was Grok

```terminal_output
potato303@raspberrypi:~ $ ./build_jc303.sh
=== Building JC-303 LV2 Plugin for ARMv7 (Pi 3B) ===
Cloning JC-303...
Cloning into '/home/potato303/jc303_src'...
remote: Enumerating objects: 1918, done.
remote: Counting objects: 100% (489/489), done.
remote: Compressing objects: 100% (133/133), done.
remote: Total 1918 (delta 392), reused 400 (delta 356), pack-reused 1429 (from 2)
Receiving objects: 100% (1918/1918), 61.39 MiB | 4.10 MiB/s, done.
Resolving deltas: 100% (918/918), done.
Updating files: 100% (469/469), done.
Configuring CMake for ARMv7 (NEON)...
-- The C compiler identification is GNU 12.4.0
-- The CXX compiler identification is GNU 12.4.0
-- Detecting C compiler ABI info
-- Detecting C compiler ABI info - done
-- Check for working C compiler: /usr/bin/gcc-12 - skipped
-- Detecting C compile features
-- Detecting C compile features - done
-- Detecting CXX compiler ABI info
-- Detecting CXX compiler ABI info - done
-- Check for working CXX compiler: /usr/bin/g++-12 - skipped
-- Detecting CXX compile features
-- Detecting CXX compile features - done
-- Found PkgConfig: /usr/bin/pkg-config (found version "1.8.1")
-- Checking for module 'alsa'
--   Found alsa, version 1.2.14
-- Checking for modules 'freetype2;fontconfig'
--   Found freetype2, version 26.2.20
--   Found fontconfig, version 2.15.0
-- Checking for module 'gl'
--   Found gl, version 1.2
-- Checking for module 'libcurl'
--   Found libcurl, version 8.14.1
-- Checking for modules 'webkit2gtk-4.1;gtk+-x11-3.0'
--   Found webkit2gtk-4.1, version 2.48.0
--   Found gtk+-x11-3.0, version 3.24.49
-- Configuring juceaide
-- Building juceaide
-- Exporting juceaide
-- Testing juceaide
-- Finished setting up juceaide
-- Building CLAP with CLAP_CXX_STANDARD=14
-- CLAP version: 1.2.0
CMake Warning (dev) at lib/juce-clap-extensions-src/clap-libs/clap-helpers/CMakeLists.txt:90 (install):
  Policy CMP0177 is not set: install() DESTINATION paths are normalized.  Run
  "cmake --help-policy CMP0177" for policy details.  Use the cmake_policy
  command to set the policy and suppress this warning.
This warning is for project developers.  Use -Wno-dev to suppress it.

-- Adding ChowDSP JUCE modules...
-- Performing Test CMAKE_HAVE_LIBC_PTHREAD
-- Performing Test CMAKE_HAVE_LIBC_PTHREAD - Success
-- Found Threads: TRUE
-- Creating CLAP JC303_CLAP from JC303
-- Setting Misbehaviour handler level to 'Ignore'
-- Setting Checking handler level to 'Minimal'
-- Setting event resolution to 0 samples (no sample-accurate automation)
-- Setting "Always split block" to OFF
-- Setting "Use JUCE parameter ranges" to OFF
CMake Deprecation Warning at lib/rtneural-src/CMakeLists.txt:1 (cmake_minimum_required):
  Compatibility with CMake < 3.10 will be removed from a future version of
  CMake.

  Update the VERSION argument <min> value.  Or, use the <min>...<max> syntax
  to tell CMake that the project requires at least <min> but has been updated
  to work with policies introduced by <max> or earlier.


-- RTNeural -- Using xsimd backend
-- Setting GNU compiler flags
-- Performing Test COMPILER_OPT_ARCH_AVX_SUPPORTED
-- Performing Test COMPILER_OPT_ARCH_AVX_SUPPORTED - Failed
-- Compiler DOES NOT supports flags: -mavx -mfma
-- Configuring done (954.7s)
-- Generating done (1.5s)
CMake Warning:
  Manually-specified variables were not used by the project:

    JUCE_HEADLESS_PLUGIN_CLIENT
    JUCE_USE_CURL
    JUCE_WEB_BROWSER


-- Build files have been written to: /home/potato303/jc303_src/build
Compiling project... (this will take a long time)
[  0%] Building CXX object /home/potato303/jc303_src/lib/juce-clap-extensions-build/CMakeFiles/clap_juce_extensions.dir/src/extensions/clap-juce-extensions.cpp.o
[  1%] Linking CXX static library libclap_juce_extensions.a
[  1%] Built target clap_juce_extensions
[  1%] Generating juce_binarydata_BinaryData/JuceLibraryCode/BinaryData1.cpp, juce_binarydata_BinaryData/JuceLibraryCode/BinaryData2.cpp, juce_binarydata_BinaryData/JuceLibraryCode/BinaryData3.cpp, juce_binarydata_BinaryData/JuceLibraryCode/BinaryData4.cpp, juce_binarydata_BinaryData/JuceLibraryCode/BinaryData.h
[  2%] Building CXX object src/gui/midilab/CMakeFiles/BinaryData.dir/juce_binarydata_BinaryData/JuceLibraryCode/BinaryData1.cpp.o
[  3%] Building CXX object src/gui/midilab/CMakeFiles/BinaryData.dir/juce_binarydata_BinaryData/JuceLibraryCode/BinaryData2.cpp.o
[  4%] Building CXX object src/gui/midilab/CMakeFiles/BinaryData.dir/juce_binarydata_BinaryData/JuceLibraryCode/BinaryData3.cpp.o
[  4%] Building CXX object src/gui/midilab/CMakeFiles/BinaryData.dir/juce_binarydata_BinaryData/JuceLibraryCode/BinaryData4.cpp.o
[  5%] Linking CXX static library libBinaryData.a
[  5%] Built target BinaryData
[  6%] Building CXX object /home/potato303/jc303_src/lib/rtneural-build/RTNeural/CMakeFiles/RTNeural.dir/RTNeural.cpp.o
[  7%] Linking CXX static library libRTNeural.a
[  7%] Built target RTNeural
[  8%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/dsp_accelerated_sse_or_arm.dir/processors/drive/neural_utils/RNNAccelerated.cpp.o
[  8%] Linking CXX static library libdsp_accelerated_sse_or_arm.a
[  8%] Built target dsp_accelerated_sse_or_arm
[  9%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/dsp_accelerated_avx.dir/processors/drive/neural_utils/RNNAccelerated.cpp.o
[ 10%] Linking CXX static library libdsp_accelerated_avx.a
[ 10%] Built target dsp_accelerated_avx
[ 11%] Generating juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData1.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData2.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData3.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData4.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData5.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData6.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData7.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData8.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData9.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData10.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData11.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData12.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData13.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData14.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData15.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData16.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData17.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData18.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData19.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData20.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData21.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData22.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData23.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData24.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData25.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData26.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData27.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData28.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData29.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData30.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData31.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData32.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData33.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData34.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData35.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData36.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData37.cpp, juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryDataGuitarMLModels.h
[ 12%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData1.cpp.o
[ 13%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData2.cpp.o
[ 13%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData3.cpp.o
[ 14%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData4.cpp.o
[ 15%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData5.cpp.o
[ 16%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData6.cpp.o
[ 17%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData7.cpp.o
[ 17%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData8.cpp.o
[ 18%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData9.cpp.o
[ 19%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData10.cpp.o
[ 20%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData11.cpp.o
[ 21%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData12.cpp.o
[ 21%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData13.cpp.o
[ 22%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData14.cpp.o
[ 23%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData15.cpp.o
[ 24%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData16.cpp.o
[ 25%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData17.cpp.o
[ 25%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData18.cpp.o
[ 26%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData19.cpp.o
[ 27%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData20.cpp.o
[ 28%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData21.cpp.o
[ 29%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData22.cpp.o
[ 29%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData23.cpp.o
[ 30%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData24.cpp.o
[ 31%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData25.cpp.o
[ 32%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData26.cpp.o
[ 32%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData27.cpp.o
[ 33%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData28.cpp.o
[ 34%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData29.cpp.o
[ 35%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData30.cpp.o
[ 36%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData31.cpp.o
[ 36%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData32.cpp.o
[ 37%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData33.cpp.o
[ 38%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData34.cpp.o
[ 39%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData35.cpp.o
[ 40%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData36.cpp.o
[ 40%] Building CXX object src/dsp/guitarml-byod/CMakeFiles/BinaryDataGuitarMLModels.dir/juce_binarydata_BinaryDataGuitarMLModels/JuceLibraryCode/BinaryData37.cpp.o
[ 41%] Linking CXX static library libBinaryDataGuitarMLModels.a
[ 41%] Built target BinaryDataGuitarMLModels
[ 42%] Generating JC303_artefacts/JuceLibraryCode/JuceHeader.h
[ 43%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/GlobalFunctions.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
[ 44%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_AcidPattern.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_AcidPattern.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_AcidPattern.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_AcidPattern.h:6:
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h: In instantiation of 'void rosic::circularShift(T*, int, int) [with T = AcidNote]':
/home/potato303/jc303_src/src/dsp/open303/rosic_AcidPattern.cpp:39:23:   required from here
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:179:57: warning: conversion to 'unsigned int' from 'int' may change the sign of the result -Wsign-conversion]
  179 |       memcpy(  tmp,                buffer,              na*sizeof(T));
      |                                                         ^~
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:180:55: warning: conversion to 'unsigned int' from 'int' may change the sign of the result -Wsign-conversion]
  180 |       memmove( buffer,            &buffer[na], (length-na)*sizeof(T));
      |                                                ~~~~~~~^~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:181:57: warning: conversion to 'unsigned int' from 'int' may change the sign of the result -Wsign-conversion]
  181 |       memcpy( &buffer[length-na],  tmp,                 na*sizeof(T));
      |                                                         ^~
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:185:57: warning: conversion to 'unsigned int' from 'int' may change the sign of the result -Wsign-conversion]
  185 |       memcpy(  tmp,        &buffer[length-na],          na*sizeof(T));
      |                                                         ^~
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:186:55: warning: conversion to 'unsigned int' from 'int' may change the sign of the result -Wsign-conversion]
  186 |       memmove(&buffer[na],  buffer,            (length-na)*sizeof(T));
      |                                                ~~~~~~~^~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:187:57: warning: conversion to 'unsigned int' from 'int' may change the sign of the result -Wsign-conversion]
  187 |       memcpy(  buffer,      tmp,                        na*sizeof(T));
      |                                                         ^~
[ 44%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_AcidSequencer.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_AcidPattern.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_AcidSequencer.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_AcidSequencer.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
[ 45%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_AnalogEnvelope.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_AnalogEnvelope.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_AnalogEnvelope.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_AnalogEnvelope.cpp: In member function 'void rosic::AnalogEnvelope::noteOn(bool, int, int)':
/home/potato303/jc303_src/src/dsp/open303/rosic_AnalogEnvelope.cpp:152:61: warning: unused parameter 'newKey' [-Wunused-parameter]
  152 | void AnalogEnvelope::noteOn(bool startFromCurrentLevel, int newKey, int newVel)
      |                                                         ~~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_AnalogEnvelope.cpp:152:73: warning: unused parameter 'newVel' [-Wunused-parameter]
  152 | logEnvelope::noteOn(bool startFromCurrentLevel, int newKey, int newVel)
      |                                                             ~~~~^~~~~~

[ 46%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_BiquadFilter.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_BiquadFilter.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_BiquadFilter.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
[ 47%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_BlendOscillator.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:6,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_MipMappedWaveTable.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_BlendOscillator.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_BlendOscillator.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.h:8,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_MipMappedWaveTable.h:6:
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h: In member function 'bool rosic::Complex::operator==(const rosic::Complex&) const':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:56:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   56 |       if( re == z.re && im == z.im )
      |           ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:56:28: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   56 |       if( re == z.re && im == z.im )
      |                         ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h: In member function 'bool rosic::Complex::operator!=(const rosic::Complex&) const':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:65:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   65 |       if( re != z.re || im != z.im )
      |           ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:65:28: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   65 |       if( re != z.re || im != z.im )
      |                         ~~~^~~~~~~
In file included from /home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:6:
/home/potato303/jc303_src/src/dsp/open303/rosic_BlendOscillator.h: In member function 'double rosic::BlendOscillator::getSample()':
/home/potato303/jc303_src/src/dsp/open303/GlobalDefinitions.h:91:31: warning: dereferencing type-punned pointer will break strict-aliasing rules [-Wstrict-aliasing]
   91 | #define EXPOFDBL(value) (((*((reinterpret_cast<UINT64 *>(&value)))&0x7FFFFFFFFFFFFFFFULL)>>52)-1023)
      |                             ~~^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_BlendOscillator.h:146:26: note:in expansion of macro 'EXPOFDBL'
  146 |     tableNumber  = ((int)EXPOFDBL(increment));
      |                          ^~~~~~~~
[ 48%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_Complex.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h: In member function 'bool rosic::Complex::operator==(const rosic::Complex&) const':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:56:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   56 |       if( re == z.re && im == z.im )
      |           ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:56:28: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   56 |       if( re == z.re && im == z.im )
      |                         ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h: In member function 'bool rosic::Complex::operator!=(const rosic::Complex&) const':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:65:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   65 |       if( re != z.re || im != z.im )
      |           ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:65:28: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   65 |       if( re != z.re || im != z.im )
      |                         ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp: In member function 'double rosic::Complex::getAngle()':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp:39:9: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   39 |   if((re==0.0) && (im==0))
      |       ~~^~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp:39:22: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   39 |   if((re==0.0) && (im==0))
      |                    ~~^~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp: In member function 'bool rosic::Complex::isReal()':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp:81:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   81 |   return (im == 0.0);
      |           ~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp: In member function 'bool rosic::Complex::isImaginary()':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp:86:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   86 |   return (re == 0.0);
      |           ~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp: In member function 'bool rosic::Complex::isInfinite()':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp:91:10: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   91 |   if( re == INF || re == NEG_INF || im == INF || im == NEG_INF )
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp:91:23: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   91 |   if( re == INF || re == NEG_INF || im == INF || im == NEG_INF )
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp:91:40: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   91 |   if( re == INF || re == NEG_INF || im == INF || im == NEG_INF )
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.cpp:91:53: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   91 |   if( re == INF || re == NEG_INF || im == INF || im == NEG_INF )
[ 48%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_DecayEnvelope.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_DecayEnvelope.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_DecayEnvelope.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
[ 49%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_EllipticQuarterBandFilter.cpp.o
[ 50%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_FourierTransformerRadix2.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.h:8,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h: In member function 'bool rosic::Complex::operator==(const rosic::Complex&) const':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:56:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   56 |       if( re == z.re && im == z.im )
      |           ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:56:28: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   56 |       if( re == z.re && im == z.im )
      |                         ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h: In member function 'bool rosic::Complex::operator!=(const rosic::Complex&) const':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:65:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   65 |       if( re != z.re || im != z.im )
      |           ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:65:28: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   65 |       if( re != z.re || im != z.im )
      |                         ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp: In member function 'void rosic::FourierTransformerRadix2::setBlockSize(int)':
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp:39:41: warning: conversion to 'unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
   39 |   if( newBlockSize >= 2 && isPowerOfTwo(newBlockSize) )
      |                                         ^~~~~~~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp:63:26: warning: conversion to 'unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
   63 |   else if( !isPowerOfTwo(newBlockSize) || newBlockSize <= 1 )
      |                          ^~~~~~~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp: In member function 'void rosic::FourierTransformerRadix2::setRealSignalMode(bool)':
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp:95:55: warning: unused parameter 'willBeUsedForRealSignals' [-Wunused-parameter]
   95 | void FourierTransformerRadix2::setRealSignalMode(bool willBeUsedForRealSignals)
      |                                                  ~~~~~^~~~~~~~~~~~~~~~~~~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp: In member function 'void rosic::FourierTransformerRadix2::transformComplexBufferInPlace(rosic::Complex*)':
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp:110:27: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
  110 |   if( normalizationFactor != 1.0 )
      |       ~~~~~~~~~~~~~~~~~~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp: In member function 'void rosic::FourierTransformerRadix2::transformComplexBuffer(rosic::Complex*, rosic::Complex*)':
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp:134:27: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
  134 |   if( normalizationFactor != 1.0 )
      |       ~~~~~~~~~~~~~~~~~~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp: In member function 'void rosic::FourierTransformerRadix2::transformRealSignal(double*, rosic::Complex*)':
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp:167:27: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
  167 |   if( normalizationFactor != 1.0 )
      |       ~~~~~~~~~~~~~~~~~~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp: In member function 'void rosic::FourierTransformerRadix2::getRealSignalMagnitudesAndPhases(double*, double*, double*)':
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp:213:12: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
  213 |     if( re == 0.0 && im == 0.0 )
      |         ~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp:213:25: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
  213 |     if( re == 0.0 && im == 0.0 )
      |                      ~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp: In member function 'void rosic::FourierTransformerRadix2::transformSymmetricSpectrum(rosic::Complex*, double*)':
/home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.cpp:246:27: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
  246 |   if( normalizationFactor != 1.0 )
      |       ~~~~~~~~~~~~~~~~~~~~^~~~~~
[ 51%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_FunctionTemplates.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:6,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
[ 52%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_LeakyIntegrator.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_LeakyIntegrator.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_LeakyIntegrator.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_LeakyIntegrator.cpp: In member function 'void rosic::LeakyIntegrator::setTimeConstant(double)':
/home/potato303/jc303_src/src/dsp/open303/rosic_LeakyIntegrator.cpp:35:49: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   35 |   if( newTimeConstant >= 0.0 && newTimeConstant != tau )
      |                                 ~~~~~~~~~~~~~~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_LeakyIntegrator.cpp: In static member function 'static double rosic::LeakyIntegrator::getNormalizer(double, double, double)':
/home/potato303/jc303_src/src/dsp/open303/rosic_LeakyIntegrator.cpp:51:10: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   51 |   if( ta == 0.0 && td == 0.0 )
      |       ~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_LeakyIntegrator.cpp:51:23: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   51 |   if( ta == 0.0 && td == 0.0 )
      |                    ~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_LeakyIntegrator.cpp:53:15: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   53 |   else if( ta == 0.0 )
      |            ~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_LeakyIntegrator.cpp:57:15: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   57 |   else if( td == 0.0 )
      |            ~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_LeakyIntegrator.cpp:72:10: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   72 |   if( ta == td )
      |       ~~~^~~~~
[ 52%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_MidiNoteEvent.cpp.o
[ 53%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_MipMappedWaveTable.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:6,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_MipMappedWaveTable.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_MipMappedWaveTable.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.h:8,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_MipMappedWaveTable.h:6:
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h: In member function 'bool rosic::Complex::operator==(const rosic::Complex&) const':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:56:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   56 |       if( re == z.re && im == z.im )
      |           ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:56:28: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   56 |       if( re == z.re && im == z.im )
      |                         ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h: In member function 'bool rosic::Complex::operator!=(const rosic::Complex&) const':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:65:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   65 |       if( re != z.re || im != z.im )
      |           ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:65:28: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   65 |       if( re != z.re || im != z.im )
      |                         ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h: In instantiation of 'void rosic::circularShift(T*, int, int) [with T = double]':
/home/potato303/jc303_src/src/dsp/open303/rosic_MipMappedWaveTable.cpp:264:16:   required from here
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:179:57: warning: conversion to 'unsigned int' from 'int' may change the sign of the result -Wsign-conversion]
  179 |       memcpy(  tmp,                buffer,              na*sizeof(T));
      |                                                         ^~
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:180:55: warning: conversion to 'unsigned int' from 'int' may change the sign of the result -Wsign-conversion]
  180 |       memmove( buffer,            &buffer[na], (length-na)*sizeof(T));
      |                                                ~~~~~~~^~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:181:57: warning: conversion to 'unsigned int' from 'int' may change the sign of the result -Wsign-conversion]
  181 |       memcpy( &buffer[length-na],  tmp,                 na*sizeof(T));
      |                                                         ^~
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:185:57: warning: conversion to 'unsigned int' from 'int' may change the sign of the result -Wsign-conversion]
  185 |       memcpy(  tmp,        &buffer[length-na],          na*sizeof(T));
      |                                                         ^~
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:186:55: warning: conversion to 'unsigned int' from 'int' may change the sign of the result -Wsign-conversion]
  186 |       memmove(&buffer[na],  buffer,            (length-na)*sizeof(T));
      |                                                ~~~~~~~^~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:187:57: warning: conversion to 'unsigned int' from 'int' may change the sign of the result -Wsign-conversion]
  187 |       memcpy(  buffer,      tmp,                        na*sizeof(T));
      |                                                         ^~
/home/potato303/jc303_src/src/dsp/open303/rosic_MipMappedWaveTable.cpp: In member function 'rosic::MipMappedWaveTable::initPrototypeTable()':
/home/potato303/jc303_src/src/dsp/open303/rosic_MipMappedWaveTable.cpp:70:23: warning: iteration 2048 invokes undefined behavior [-Waggressive-loop-optimizations]
   70 |     prototypeTable[i] = 0.0;
      |     ~~~~~~~~~~~~~~~~~~^~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_MipMappedWaveTable.cpp:69:17: note: within this loop
   69 |   for(int i=0; i<(tableLength+4); i++)
      |                ~^~~~~~~~~~~~~~~~
[ 54%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_NumberManipulations.cpp.o
[ 55%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_OnePoleFilter.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_OnePoleFilter.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_OnePoleFilter.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
[ 56%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_Open303.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_FunctionTemplates.h:6,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_MipMappedWaveTable.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_BlendOscillator.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_Open303.h:6,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_Open303.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_FourierTransformerRadix2.h:8,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_MipMappedWaveTable.h:6:
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h: In member function 'bool rosic::Complex::operator==(const rosic::Complex&) const':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:56:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   56 |       if( re == z.re && im == z.im )
      |           ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:56:28: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   56 |       if( re == z.re && im == z.im )
      |                         ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h: In member function 'bool rosic::Complex::operator!=(const rosic::Complex&) const':
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:65:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   65 |       if( re != z.re || im != z.im )
      |           ~~~^~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Complex.h:65:28: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   65 |       if( re != z.re || im != z.im )
      |                         ~~~^~~~~~~
In file included from /home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:6:
/home/potato303/jc303_src/src/dsp/open303/rosic_BlendOscillator.h: In member function 'double rosic::BlendOscillator::getSample()':
/home/potato303/jc303_src/src/dsp/open303/GlobalDefinitions.h:91:31: warning: dereferencing type-punned pointer will break strict-aliasing rules [-Wstrict-aliasing]
   91 | #define EXPOFDBL(value) (((*((reinterpret_cast<UINT64 *>(&value)))&0x7FFFFFFFFFFFFFFFULL)>>52)-1023)
      |                             ~~^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_BlendOscillator.h:146:26: note:in expansion of macro 'EXPOFDBL'
  146 |     tableNumber  = ((int)EXPOFDBL(increment));
      |                          ^~~~~~~~
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_Open303.h:8:
/home/potato303/jc303_src/src/dsp/open303/rosic_TeeBeeFilter.h: In member function 'void rosic::TeeBeeFilter::setCutoff(double, bool)':
/home/potato303/jc303_src/src/dsp/open303/rosic_TeeBeeFilter.h:152:19: warning:comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
  152 |     if( newCutoff != cutoff )
      |         ~~~~~~~~~~^~~~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Open303.cpp: In member function 'void rosic::Open303::noteOn(int, int, double)':
/home/potato303/jc303_src/src/dsp/open303/rosic_Open303.cpp:144:59: warning: unused parameter 'detune' [-Wunused-parameter]
  144 | void Open303::noteOn(int noteNumber, int velocity, double detune)
      |                                                    ~~~~~~~^~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Open303.cpp: In member function 'void rosic::Open303::releaseNote(int)':
/home/potato303/jc303_src/src/dsp/open303/rosic_Open303.cpp:267:31: warning: unused parameter 'noteNumber' [-Wunused-parameter]
  267 | void Open303::releaseNote(int noteNumber)
      |                           ~~~~^~~~~~~~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_Open303.cpp: In member function 'void rosic::Open303::calculateEnvModScalerAndOffset()':
/home/potato303/jc303_src/src/dsp/open303/rosic_Open303.cpp:319:19: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
  319 |     if( envScaler != 0.0 ) // avoid division by zero
      |         ~~~~~~~~~~^~~~~~
[ 56%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_RealFunctions.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
[ 57%] Building CXX object CMakeFiles/JC303.dir/src/dsp/open303/rosic_TeeBeeFilter.cpp.o
In file included from /home/potato303/jc303_src/src/dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_OnePoleFilter.h:5,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_TeeBeeFilter.h:8,
                 from /home/potato303/jc303_src/src/dsp/open303/rosic_TeeBeeFilter.cpp:1:
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
/home/potato303/jc303_src/src/dsp/open303/rosic_TeeBeeFilter.h: In member function 'void rosic::TeeBeeFilter::setCutoff(double, bool)':
/home/potato303/jc303_src/src/dsp/open303/rosic_TeeBeeFilter.h:152:19: warning:comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
  152 |     if( newCutoff != cutoff )
      |         ~~~~~~~~~~^~~~~~~~~
[ 58%] Building CXX object CMakeFiles/JC303.dir/src/gui/midilab/Gui.cpp.o
In file included from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/third_party/pfr/include/pfr/detail/core_name.hpp:23,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/third_party/pfr/include/pfr/core_name.hpp:17,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/third_party/pfr/include/pfr.hpp:14,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/chowdsp_reflection.h:31,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_data_structures/Structures/chowdsp_EnumMap.h:4,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_data_structures/chowdsp_data_structures.h:44,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_filters/chowdsp_filters.h:23,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_dsp_utils/chowdsp_dsp_utils.h:37,
                 from /home/potato303/jc303_src/build/JC303_artefacts/JuceLibraryCode/JuceHeader.h:27,
                 from /home/potato303/jc303_src/src/gui/midilab/Gui.h:3,
                 from /home/potato303/jc303_src/src/gui/midilab/Gui.cpp:1:
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/third_party/pfr/include/pfr/detail/core_name20_static.hpp: In constructor 'consteval pfr::detail::backward::backward(std::string_view)':
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/third_party/pfr/include/pfr/detail/core_name20_static.hpp:54:50: warning: declaration of 'value' shadows a member of 'pfr::detail::backward' [-Wshadow]
   54 |     explicit consteval backward(std::string_view value) noexcept
      |                                 ~~~~~~~~~~~~~~~~~^~~~~
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/third_party/pfr/include/pfr/detail/core_name20_static.hpp:58:22: note: shadowed declaration is here
   58 |     std::string_view value;
      |                      ^~~~~
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/third_party/pfr/include/pfr/detail/core_name20_static.hpp: In constructor 'consteval pfr::detail::backward::backward(std::string_view)':
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/third_party/pfr/include/pfr/detail/core_name20_static.hpp:54:50: warning: declaration of 'value' shadows a member of 'pfr::detail::backward' [-Wshadow]
   54 |     explicit consteval backward(std::string_view value) noexcept
      |                                 ~~~~~~~~~~~~~~~~~^~~~~
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/third_party/pfr/include/pfr/detail/core_name20_static.hpp:58:22: note: shadowed declaration is here
   58 |     std::string_view value;
      |                      ^~~~~
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/third_party/pfr/include/pfr/detail/core_name20_static.hpp: In constructor 'consteval pfr::detail::backward::backward(std::string_view)':
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/third_party/pfr/include/pfr/detail/core_name20_static.hpp:54:50: warning: declaration of 'value' shadows a member of 'pfr::detail::backward' [-Wshadow]
   54 |     explicit consteval backward(std::string_view value) noexcept
      |                                 ~~~~~~~~~~~~~~~~~^~~~~
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_reflection/third_party/pfr/include/pfr/detail/core_name20_static.hpp:58:22: note: shadowed declaration is here
   58 |     std::string_view value;
      |                      ^~~~~
In file included from /home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_RealFunctions.h:9,
                 from /home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_FunctionTemplates.h:6,
                 from /home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_MipMappedWaveTable.h:5,
                 from /home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_BlendOscillator.h:5,
                 from /home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_Open303.h:6,
                 from /home/potato303/jc303_src/src/gui/midilab/../../JC303.h:6,
                 from /home/potato303/jc303_src/src/gui/midilab/Gui.h:4:
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/GlobalFunctions.h: In function 'double randomUniform(double, double, int)':
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/GlobalFunctions.h:409:13: warning: conversion to 'long unsigned int' from 'int' may change the sign of the result [-Wsign-conversion]
  409 |     state = seed;                                        // initialization, if desired
      |             ^~~~
In file included from /home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_FourierTransformerRadix2.h:8,
                 from /home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_MipMappedWaveTable.h:6:
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_Complex.h: In member function 'bool rosic::Complex::operator==(const rosic::Complex&) const':
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_Complex.h:56:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   56 |       if( re == z.re && im == z.im )
      |           ~~~^~~~~~~
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_Complex.h:56:28: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   56 |       if( re == z.re && im == z.im )
      |                         ~~~^~~~~~~
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_Complex.h: In member function 'bool rosic::Complex::operator!=(const rosic::Complex&) const':
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_Complex.h:65:14: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   65 |       if( re != z.re || im != z.im )
      |           ~~~^~~~~~~
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_Complex.h:65:28: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
   65 |       if( re != z.re || im != z.im )
      |                         ~~~^~~~~~~
In file included from /home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/GlobalFunctions.h:6:
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_BlendOscillator.h: In member function 'double rosic::BlendOscillator::getSample()':
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/GlobalDefinitions.h:91:31: warning: dereferencing type-punned pointer will break strict-aliasing rules [-Wstrict-aliasing]
   91 | #define EXPOFDBL(value) (((*((reinterpret_cast<UINT64 *>(&value)))&0x7FFFFFFFFFFFFFFFULL)>>52)-1023)
      |                             ~~^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/GlobalDefinitions.h:91:31: note: in definition of macro 'EXPOFDBL'
   91 | #define EXPOFDBL(value) (((*((reinterpret_cast<UINT64 *>(&value)))&0x7FFFFFFFFFFFFFFFULL)>>52)-1023)
      |                               ^~~~~~~~~~~~~~~~
In file included from /home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_Open303.h:8:
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_TeeBeeFilter.h: In member function 'void rosic::TeeBeeFilter::setCutoff(double, bool)':
/home/potato303/jc303_src/src/gui/midilab/../../dsp/open303/rosic_TeeBeeFilter.h:152:19: warning: comparing floating-point with '==' or '!=' is unsafe [-Wfloat-equal]
  152 |     if( newCutoff != cutoff )
      |         ~~~~~~~~~~^~~~~~~~~
In file included from /home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Model.h:6,
                 from /home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/RTNeural.h:23,
                 from /home/potato303/jc303_src/src/gui/midilab/../../dsp/guitarml-byod/processors/drive/neural_utils/../../../pch.h:20,
                 from /home/potato303/jc303_src/src/gui/midilab/../../dsp/guitarml-byod/processors/drive/neural_utils/ResampledRNNAccelerated.h:5,
                 from /home/potato303/jc303_src/src/gui/midilab/../../dsp/guitarml-byod/processors/drive/GuitarMLAmp.h:3,
                 from /home/potato303/jc303_src/src/gui/midilab/../../JC303.h:1:
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Layer.h: In constructor 'RTNeural::Layer<T>::Layer(int, int)':
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Layer.h:16:28: warning: declaration of 'out_size' shadows a member of 'RTNeural::Layer<T>' [-Wshadow]
   16 |     Layer(int in_size, int out_size)
      |                        ~~~~^~~~~~~~
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Layer.h:34:15: note: shadowed declaration is here
   34 |     const int out_size;
      |               ^~~~~~~~
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Layer.h:16:15: warning: declaration of 'in_size' shadows a member of 'RTNeural::Layer<T>' [-Wshadow]
   16 |     Layer(int in_size, int out_size)
      |           ~~~~^~~~~~~
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Layer.h:33:15: note: shadowed declaration is here
   33 |     const int in_size;
      |               ^~~~~~~
In file included from /home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Model.h:7:
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/activation/activation.h: In constructor 'RTNeural::Activation<T>::Activation(int, std::function<FloatType(FloatType)>, const std::string&)':
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/activation/activation.h:16:71: warning: declaration of 'name' shadows a member of 'RTNeural::Activation<T>' [-Wshadow]
   16 | Activation(int size, std::function<T(T)> func, const std::string& name)
      |                                                ~~~~~~~~~~~~~~~~~~~^~~~

/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/activation/activation.h:34:23: note: shadowed declaration is here
   34 |     const std::string name;
      |                       ^~~~
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/activation/activation.h:16:46: warning: declaration of 'func' shadows a member of 'RTNeural::Activation<T>' [-Wshadow]
   16 |     Activation(int size, std::function<T(T)> func, const std::string& name)
      |                          ~~~~~~~~~~~~~~~~~~~~^~~~
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/activation/activation.h:35:31: note: shadowed declaration is here
   35 |     const std::function<T(T)> func;
      |                               ^~~~
In file included from /home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/conv1d/conv1d.h:9,
                 from /home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Model.h:12:
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/conv1d/conv1d_xsimd.tpp: In constructor 'RTNeural::Conv1D<T>::Conv1D(int, int, int, int, int)':
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/conv1d/conv1d_xsimd.tpp:7:50: warning: declaration of 'kernel_size' shadows a member of 'RTNeural::Conv1D<T>' [-Wshadow]
    7 | Conv1D<T>::Conv1D(int in_size, int out_size, int kernel_size, int dilation, int num_groups)
      |                                              ~~~~^~~~~~~~~~~
In file included from /home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/conv1d/conv1d.h:8:
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/conv1d/conv1d_xsimd.h:125:15: note: shadowed declaration is here
  125 |     const int kernel_size;
      |               ^~~~~~~~~~~
In file included from /home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/gru/gru.h:11,
                 from /home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Model.h:17:
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/gru/gru_xsimd.tpp: In constructor 'RTNeural::GRULayer<T, MathsProvider>::WeightSet::WeightSet(int, int)':
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/gru/gru_xsimd.tpp:47:67: warning: declaration of 'out_size' shadows a member of 'RTNeural::GRULayer<T, MathsProvider>::WeightSet' [-Wshadow]
   47 | ayer<T, MathsProvider>::WeightSet::WeightSet(int in_size, int out_size)
      |                                                           ~~~~^~~~~~~~

In file included from /home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/gru/gru.h:10:
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/gru/gru_xsimd.h:134:19: note: shadowed declaration is here
  134 |         const int out_size;
      |                   ^~~~~~~~
In file included from /home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/lstm/lstm.h:9,
                 from /home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Model.h:19:
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/lstm/lstm_xsimd.tpp: In constructor 'RTNeural::LSTMLayer<T, MathsProvider>::WeightSet::WeightSet(int, int)':
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/lstm/lstm_xsimd.tpp:56:68: warning: declaration of 'out_size' shadows a member of 'RTNeural::LSTMLayer<T, MathsProvider>::WeightSet' [-Wshadow]
   56 | ayer<T, MathsProvider>::WeightSet::WeightSet(int in_size, int out_size)
      |                                                           ~~~~^~~~~~~~

In file included from /home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/lstm/lstm.h:8:
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/lstm/lstm_xsimd.h:107:19: note: shadowed declaration is here
  107 |         const int out_size;
      |                   ^~~~~~~~
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Model.h: In constructor 'RTNeural::Model<T>::Model(int)':
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Model.h:36:24: warning: declaration of 'in_size' shadows a member of 'RTNeural::Model<T>' [-Wshadow]
   36 |     explicit Model(int in_size)
      |                    ~~~~^~~~~~~
/home/potato303/jc303_src/lib/rtneural-src/RTNeural/../RTNeural/Model.h:111:15:note: shadowed declaration is here
  111 |     const int in_size;
      |               ^~~~~~~
In file included from /home/potato303/jc303_src/lib/JUCE/modules/juce_audio_processors/juce_audio_processors.h:154,
                 from /home/potato303/jc303_src/lib/JUCE/modules/juce_audio_plugin_client/juce_audio_plugin_client.h:65,
                 from /home/potato303/jc303_src/build/JC303_artefacts/JuceLibraryCode/JuceHeader.h:14:
/home/potato303/jc303_src/lib/JUCE/modules/juce_audio_processors/processors/juce_AudioProcessor.h: At global scope:
/home/potato303/jc303_src/lib/JUCE/modules/juce_audio_processors/processors/juce_AudioProcessor.h:289:18: warning: 'virtual void juce::AudioProcessor::processBlock(juce::AudioBuffer<double>&, juce::MidiBuffer&)' was hidden [-Woverloaded-virtual]
  289 |     virtual void processBlock (AudioBuffer<double>& buffer,
      |                  ^~~~~~~~~~~~
In file included from /home/potato303/jc303_src/src/gui/midilab/../../dsp/guitarml-byod/processors/drive/../BaseProcessor.h:3,
                 from /home/potato303/jc303_src/src/gui/midilab/../../dsp/guitarml-byod/processors/drive/GuitarMLAmp.h:5:
/home/potato303/jc303_src/src/gui/midilab/../../dsp/guitarml-byod/processors/drive/../JuceProcWrapper.h:20:10: note:   by 'virtual void JuceProcWrapper::processBlock(juce::AudioBuffer<float>&, juce::MidiBuffer&)'
   20 |     void processBlock (AudioBuffer<float>&, MidiBuffer&) override {}
      |          ^~~~~~~~~~~~
/home/potato303/jc303_src/src/gui/midilab/../../dsp/guitarml-byod/processors/drive/../BaseProcessor.h: In constructor 'BaseProcessor::BaseProcessor(const juce::String&, ParamLayout&&, InputPort, OutputPort, juce::UndoManager*, InputPortMapper, OutputPortMapper)':
/home/potato303/jc303_src/src/gui/midilab/../../dsp/guitarml-byod/processors/drive/../BaseProcessor.h:85:34: warning: declaration of 'name' shadows a member of 'BaseProcessor' [-Wshadow]
   85 |     BaseProcessor (const String& name,
      |                    ~~~~~~~~~~~~~~^~~~
/home/potato303/jc303_src/src/gui/midilab/../../dsp/guitarml-byod/processors/drive/../JuceProcWrapper.h:40:12: note: shadowed declaration is here
   40 |     String name;
      |            ^~~~
/home/potato303/jc303_src/src/gui/midilab/../../dsp/guitarml-byod/processors/drive/../BaseProcessor.h: In member function 'bool BaseProcessor::isBypassed() const':
/home/potato303/jc303_src/src/gui/midilab/../../dsp/guitarml-byod/processors/drive/../BaseProcessor.h:110:75: warning: comparing floating-point with '==' or '!' is unsafe [-Wfloat-equal]
  110 | isBypassed() const { return ! static_cast<bool> (onOffParam->load()); }
      |                                                  ~~~~~~~~~~~~~~~~^~

/home/potato303/jc303_src/lib/JUCE/modules/juce_audio_processors/processors/juce_AudioProcessor.h: At global scope:
/home/potato303/jc303_src/lib/JUCE/modules/juce_audio_processors/processors/juce_AudioProcessor.h:1498:33: warning: 'virtual void juce::AudioProcessor::setParameter(int, float)' was hidden [-Woverloaded-virtual]
 1498 |     [[deprecated]] virtual void setParameter (int parameterIndex, float newValue);
      |                                 ^~~~~~~~~~~~
/home/potato303/jc303_src/src/gui/midilab/../../JC303.h:89:10: note:   by 'void JC303::setParameter(Open303Parameters, float)'
   89 |     void setParameter (Open303Parameters index, float value);
      |          ^~~~~~~~~~~~
In file included from /home/potato303/jc303_src/src/gui/midilab/Gui.h:5:
/home/potato303/jc303_src/src/gui/midilab/KnobLookAndFeel.h: In member function 'virtual void KnobLookAndFeel::drawRotarySlider(juce::Graphics&, int, int, int, int, float, float, float, juce::Slider&)':
/home/potato303/jc303_src/src/gui/midilab/KnobLookAndFeel.h:14:83: warning: unused parameter 'sliderPos' [-Wunused-parameter]
   14 |                   int x, int y, int width, int height, float sliderPos,
      |                                                        ~~~~~~^~~~~~~~~

/home/potato303/jc303_src/src/gui/midilab/KnobLookAndFeel.h:15:46: warning: unused parameter 'rotaryStartAngle' [-Wunused-parameter]
   15 |                                        float rotaryStartAngle, float rotaryEndAngle, juce::Slider& slider)
      |                                        ~~~~~~^~~~~~~~~~~~~~~~
/home/potato303/jc303_src/src/gui/midilab/KnobLookAndFeel.h:15:70: warning: unused parameter 'rotaryEndAngle' [-Wunused-parameter]
   15 |                               float rotaryStartAngle, float rotaryEndAngle, juce::Slider& slider)
      |                                                       ~~~~~~^~~~~~~~~~~~~~

In file included from /home/potato303/jc303_src/src/gui/midilab/Gui.h:6:
/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h: In member function 'virtual void ModKnobLookAndFeel::drawRotarySlider(juce::Graphics&, int, int, int, int, float, float, float, juce::Slider&)':
/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h:14:83: warning: unused parameter 'sliderPos' [-Wunused-parameter]
   14 |                   int x, int y, int width, int height, float sliderPos,
      |                                                        ~~~~~~^~~~~~~~~

/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h:15:46: warning: unused parameter 'rotaryStartAngle' [-Wunused-parameter]
   15 |                                        float rotaryStartAngle, float rotaryEndAngle, juce::Slider& slider)
      |                                        ~~~~~~^~~~~~~~~~~~~~~~
/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h:15:70: warning: unused parameter 'rotaryEndAngle' [-Wunused-parameter]
   15 |                               float rotaryStartAngle, float rotaryEndAngle, juce::Slider& slider)
      |                                                       ~~~~~~^~~~~~~~~~~~~~

/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h: In constructor AttachedLabel::AttachedLabel(juce::Justification)':
/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h:45:33: warning: declaration of 'justification' shadows a member of 'AttachedLabel' [-Wshadow]
   45 |     AttachedLabel(Justification justification = Justification::centredTop) :m_justification(justification) {}
      |                   ~~~~~~~~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In file included from /home/potato303/jc303_src/lib/JUCE/modules/juce_gui_basics/juce_gui_basics.h:280,
                 from /home/potato303/jc303_src/lib/JUCE/modules/juce_audio_plugin_client/juce_audio_plugin_client.h:63:
/home/potato303/jc303_src/lib/JUCE/modules/juce_gui_basics/widgets/juce_Label.h:359:19: note: shadowed declaration is here
  359 |     Justification justification = Justification::centredLeft;
      |                   ^~~~~~~~~~~~~
/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h: In constructor AttachedLabel::AttachedLabel(juce::Justification)':
/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h:45:33: warning: declaration of 'justification' shadows a member of 'AttachedLabel' [-Wshadow]
   45 |     AttachedLabel(Justification justification = Justification::centredTop) :m_justification(justification) {}
      |                   ~~~~~~~~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/home/potato303/jc303_src/lib/JUCE/modules/juce_gui_basics/widgets/juce_Label.h:359:19: note: shadowed declaration is here
  359 |     Justification justification = Justification::centredLeft;
      |                   ^~~~~~~~~~~~~
/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h: In constructor AttachedLabel::AttachedLabel(juce::Justification)':
/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h:45:33: warning: declaration of 'justification' shadows a member of 'AttachedLabel' [-Wshadow]
   45 |     AttachedLabel(Justification justification = Justification::centredTop) :m_justification(justification) {}
      |                   ~~~~~~~~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/home/potato303/jc303_src/lib/JUCE/modules/juce_gui_basics/widgets/juce_Label.h:359:19: note: shadowed declaration is here
  359 |     Justification justification = Justification::centredLeft;
      |                   ^~~~~~~~~~~~~
/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h: In member function 'void AttachedLabel::setJustification(juce::Justification)':
/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h:46:41: warning: declaration of 'justification' shadows a member of 'AttachedLabel' [-Wshadow]
   46 |     void setJustification(Justification justification) { m_justification = justification; }
      |                           ~~~~~~~~~~~~~~^~~~~~~~~~~~~
/home/potato303/jc303_src/lib/JUCE/modules/juce_gui_basics/widgets/juce_Label.h:359:19: note: shadowed declaration is here
  359 |     Justification justification = Justification::centredLeft;
      |                   ^~~~~~~~~~~~~
/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h: In member function 'virtual void AttachedLabel::componentMovedOrResized(juce::Component&, bool, bool)':
/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h:47:62: warning: unused parameter 'wasMoved' [-Wunused-parameter]
   47 |    void componentMovedOrResized (Component& component, bool wasMoved, bool wasResized)
      |                                                        ~~~~~^~~~~~~~

/home/potato303/jc303_src/src/gui/midilab/ModKnobLookAndFeel.h:47:77: warning: unused parameter 'wasResized' [-Wunused-parameter]
   47 | ntMovedOrResized (Component& component, bool wasMoved, bool wasResized)
      |                                                        ~~~~~^~~~~~~~~~

In file included from /home/potato303/jc303_src/src/gui/midilab/Gui.h:7:
/home/potato303/jc303_src/src/gui/midilab/SwitchButton.h: In member function 'virtual void SwitchButton::paintButton(juce::Graphics&, bool, bool)':
/home/potato303/jc303_src/src/gui/midilab/SwitchButton.h:14:46: warning: unused parameter 'isMouseOverButton' [-Wunused-parameter]
   14 |     void paintButton(juce::Graphics& g, bool isMouseOverButton, bool isButtonDown) override
      |                                         ~~~~~^~~~~~~~~~~~~~~~~
/home/potato303/jc303_src/src/gui/midilab/SwitchButton.h:14:70: warning: unused parameter 'isButtonDown' [-Wunused-parameter]
   14 | paintButton(juce::Graphics& g, bool isMouseOverButton, bool isButtonDow) override
      |                                                        ~~~~~^~~~~~~~~~~

/home/potato303/jc303_src/src/gui/midilab/SwitchButton.h: In member function 'virtual void SwitchButton::mouseUp(const juce::MouseEvent&)':
/home/potato303/jc303_src/src/gui/midilab/SwitchButton.h:26:42: warning: unused parameter 'event' [-Wunused-parameter]
   26 |     void mouseUp(const juce::MouseEvent& event) override
      |                  ~~~~~~~~~~~~~~~~~~~~~~~~^~~~~
In file included from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/xsimd.hpp:61,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/chowdsp_simd.h:59,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_dsp_data_structures/chowdsp_dsp_data_structures.h:28,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_filters/chowdsp_filters.h:24:
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_batch.hpp: In instantiation of 'xsimd::batch<T, A>::batch(T) [with T = double; A = xsimd::neon]':
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_math/Math/chowdsp_RandomFloat.h:64:57:   required from here
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_batch.hpp:458:69: error: too many initializers for 'xsimd::types::simd_register<double, xsimd::neon>'
  458 |         : types::simd_register<T, A>(kernel::broadcast<A>(val, A {}))
      |                                                                     ^
In file included from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_batch.hpp:448:
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/./xsimd_traits.hpp: In instantiation of 'struct xsimd::detail::static_check_supported_config_emitter<double, xsimd::neon>':
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/./xsimd_traits.hpp:84:19:   required from 'void xsimd::detail::static_check_supported_config() [with T = double; A = xsimd::neon'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_api.hpp:231:56:   required from 'xsimd::batch<U, A> xsimd::batch_cast(const batch<T, A>&) [with T_out = double; T_in = long long unsigned int; A = neon]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_math/Math/chowdsp_RandomFloat.h:64:42:   required from here
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/./xsimd_traits.hpp:64:43: error: static assertion failed: usage of batch type with unsupported type
   64 |             static_assert(!A::supported() || xsimd::has_simd_register<T, A>::value,
      |                           ~~~~~~~~~~~~~~~~^~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/./xsimd_traits.hpp:64:43: note: '((! xsimd::neon::supported()) || ((bool)std::integral_constant<bool, false>::value))' evaluates to false
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_batch.hpp: In instantiation of 'xsimd::batch<T, A>& xsimd::batch<T, A>::operator/=(const xsimd::batch<T, A>&) [with T = double; A = xsimd::neon]':
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_batch.hpp:190:32:   required from 'xsimd::batch<double> xsimd::operator/(const batch<double>&, const batch<double>&)'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_math/Math/chowdsp_RandomFloat.h:64:57:   required from here
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_batch.hpp:743:38: error: no matching function for call to 'div<xsimd::neon>(xsimd::batch<double>&, const xsimd::batch<double>&, xsimd::neon)'
  743 |         return *this = kernel::div<A>(*this, other, A {});
      |                        ~~~~~~~~~~~~~~^~~~~~~~~~~~~~~~~~~~
In file included from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/xsimd_isa.hpp:72,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_batch.hpp:446:
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/./xsimd_neon.hpp:784:32: note: candidate: 'xsimd::batch<float, A> xsimd::kernel::div(const xsimd::batch<float, A>&, const xsimd::batch<float, A>&, requires_arch<xsimd::neon>) [with A = xsimd::neon; requires_arch<xsimd::neon> = const xsimd::neon&]'
  784 |         inline batch<float, A> div(batch<float, A> const& lhs, batch<float, A> const& rhs, requires_arch<neon>) noexcept
      |                                ^~~
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/./xsimd_neon.hpp:784:59: note:   no known conversion for argument 1 from 'xsimd::batch<double>' to 'const xsimd::batch<float>&'
  784 |         inline batch<float, A> div(batch<float, A> const& lhs, batch<float, A> const& rhs, requires_arch<neon>) noexcept
      |                                    ~~~~~~~~~~~~~~~~~~~~~~~^~~
In file included from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/./xsimd_generic.hpp:15,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/xsimd_isa.hpp:84:
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_arithmetic.hpp:48:28: note: candidate: 'template<class A, class T, class> xsimd::batch<T, A> xsimd::kernel::div(const xsimd::batch<T, A>&, const xsimd::batch<T, A>&, requires_arch<xsimd::generic>)'
   48 |         inline batch<T, A> div(batch<T, A> const& self, batch<T, A> const& other, requires_arch<generic>) noexcept
      |                            ^~~
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_arithmetic.hpp:48:28: note:   template argument deduction/substitution failed:
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_arithmetic.hpp:47:37: error: no type named 'type' in 'struct std::enable_if<false, void>'
   47 |         template <class A, class T, class = typename std::enable_if<std::is_integral<T>::value, void>::type>
      |                                     ^~~~~
In file included from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/./xsimd_generic.hpp:18:
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp: In instantiation of 'xsimd::batch<T, A> xsimd::kernel::detail::batch_cast(const xsimd::batch<R, A>&, const xsimd::batch<T, A>&, xsimd::kernel::requires_arch<xsimd::generic>, with_slow_conversion) [with A = xsimd::neon; T_out = double; T_in = long long unsigned int; xsimd::kernel::requires_arch<xsimd::generic> = const xsimd::generic&]':
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:81:38   required from 'xsimd::batch<T, A> xsimd::kernel::batch_cast(const xsimd::batch<R, A>&, const xsimd::batch<T, A>&, requires_arch<xsimd::generic>) [with A = xsimd::neon; T_out = double; T_in = long long unsigned int; requires_arch<xsimd::generic> = const xsimd::generic&]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_api.hpp:233:37:   required from 'xsimd::batch<U, A> xsimd::batch_cast(const batch<T, A>&) [with T_out = double; T_in = long long unsigned int; A = neon]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_math/Math/chowdsp_RandomFloat.h:64:42:   required from here
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:68:51 error: static assertion failed: compatible sizes
   68 |                 static_assert(batch_type_in::size == batch_type_out::size, "compatible sizes");
      |                                              ~~~~~^~~~~~~~~~~~~~~~~~~~~~~
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:68:51 note: the comparison reduces to '(2 == 0)'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:72:81 error: no matching function for call to 'begin(double [0])'
   72 | :copy(std::begin(buffer_in), std::end(buffer_in), std::begin(buffer_out);
      |                                                   ~~~~~~~~~~^~~~~~~~~~~

In file included from /usr/include/c++/12/bits/algorithmfwd.h:39,
                 from /usr/include/c++/12/bits/stl_algo.h:59,
                 from /usr/include/c++/12/algorithm:61,
                 from /home/potato303/jc303_src/lib/JUCE/modules/juce_core/system/juce_StandardHeader.h:62,
                 from /home/potato303/jc303_src/lib/JUCE/modules/juce_core/juce_core.h:215,
                 from /home/potato303/jc303_src/lib/JUCE/modules/juce_graphics/juce_graphics.h:67,
                 from /home/potato303/jc303_src/lib/JUCE/modules/juce_gui_basics/juce_gui_basics.h:68:
/usr/include/c++/12/initializer_list:90:5: note: candidate: 'template<class _Tp> constexpr const _Tp* std::begin(initializer_list<_Tp>)'
   90 |     begin(initializer_list<_Tp> __ils) noexcept
      |     ^~~~~
/usr/include/c++/12/initializer_list:90:5: note:   template argument deduction/substitution failed:
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:72:81 note:   mismatched types 'std::initializer_list<_Tp>' and 'double*'
   72 | :copy(std::begin(buffer_in), std::end(buffer_in), std::begin(buffer_out);
      |                                                   ~~~~~~~~~~^~~~~~~~~~~

In file included from /usr/include/c++/12/array:44,
                 from /home/potato303/jc303_src/lib/JUCE/modules/juce_core/system/juce_StandardHeader.h:63:
/usr/include/c++/12/bits/range_access.h:52:5: note: candidate: 'template<class _Container> constexpr decltype (__cont.begin()) std::begin(_Container&)'
   52 |     begin(_Container& __cont) -> decltype(__cont.begin())
      |     ^~~~~
/usr/include/c++/12/bits/range_access.h:52:5: note:   template argument deduction/substitution failed:
/usr/include/c++/12/bits/range_access.h: In substitution of 'template<class _Container> constexpr decltype (__cont.begin()) std::begin(_Container&) [with _Container = double [0]]':
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:72:81   required from 'xsimd::batch<T, A> xsimd::kernel::detail::batch_cast(const xsimd::batch<R, A>&, const xsimd::batch<T, A>&, xsimd::kernel::requires_arch<xsimd::generic>, with_slow_conversion) [with A = xsimd::neon; T_out = double; T_in = long long unsigned int; xsimd::kernel::requires_arch<xsimd::generic> = const xsimd::generic&]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:81:38   required from 'xsimd::batch<T, A> xsimd::kernel::batch_cast(const xsimd::batch<R, A>&, const xsimd::batch<T, A>&, requires_arch<xsimd::generic>) [with A = xsimd::neon; T_out = double; T_in = long long unsigned int; requires_arch<xsimd::generic> = const xsimd::generic&]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_api.hpp:233:37:   required from 'xsimd::batch<U, A> xsimd::batch_cast(const batch<T, A>&) [with T_out = double; T_in = long long unsigned int; A = neon]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_math/Math/chowdsp_RandomFloat.h:64:42:   required from here
/usr/include/c++/12/bits/range_access.h:52:50: error: request for member 'begin' in '__cont', which is of non-class type 'double [0]'
   52 |     begin(_Container& __cont) -> decltype(__cont.begin())
      |                                           ~~~~~~~^~~~~
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp: In instantiation of 'xsimd::batch<T, A> xsimd::kernel::detail::batch_cast(const xsimd::batch<R, A>&, const xsimd::batch<T, A>&, xsimd::kernel::requires_arch<xsimd::generic>, with_slow_conversion) [with A = xsimd::neon; T_out = double; T_in = long long unsigned int; xsimd::kernel::requires_arch<xsimd::generic> = const xsimd::generic&]':
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:81:38   required from 'xsimd::batch<T, A> xsimd::kernel::batch_cast(const xsimd::batch<R, A>&, const xsimd::batch<T, A>&, requires_arch<xsimd::generic>) [with A = xsimd::neon; T_out = double; T_in = long long unsigned int; requires_arch<xsimd::generic> = const xsimd::generic&]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_api.hpp:233:37:   required from 'xsimd::batch<U, A> xsimd::batch_cast(const batch<T, A>&) [with T_out = double; T_in = long long unsigned int; A = neon]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_math/Math/chowdsp_RandomFloat.h:64:42:   required from here
/usr/include/c++/12/bits/range_access.h:63:5: note: candidate: 'template<class _Container> constexpr decltype (__cont.begin()) std::begin(const _Container&)'
   63 |     begin(const _Container& __cont) -> decltype(__cont.begin())
      |     ^~~~~
/usr/include/c++/12/bits/range_access.h:63:5: note:   template argument deduction/substitution failed:
/usr/include/c++/12/bits/range_access.h: In substitution of 'template<class _Container> constexpr decltype (__cont.begin()) std::begin(const _Container&) [with _Container = double [0]]':
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:72:81   required from 'xsimd::batch<T, A> xsimd::kernel::detail::batch_cast(const xsimd::batch<R, A>&, const xsimd::batch<T, A>&, xsimd::kernel::requires_arch<xsimd::generic>, with_slow_conversion) [with A = xsimd::neon; T_out = double; T_in = long long unsigned int; xsimd::kernel::requires_arch<xsimd::generic> = const xsimd::generic&]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:81:38   required from 'xsimd::batch<T, A> xsimd::kernel::batch_cast(const xsimd::batch<R, A>&, const xsimd::batch<T, A>&, requires_arch<xsimd::generic>) [with A = xsimd::neon; T_out = double; T_in = long long unsigned int; requires_arch<xsimd::generic> = const xsimd::generic&]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_api.hpp:233:37:   required from 'xsimd::batch<U, A> xsimd::batch_cast(const batch<T, A>&) [with T_out = double; T_in = long long unsigned int; A = neon]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_math/Math/chowdsp_RandomFloat.h:64:42:   required from here
/usr/include/c++/12/bits/range_access.h:63:56: error: request for member 'begin' in '__cont', which is of non-class type 'const double [0]'
   63 |     begin(const _Container& __cont) -> decltype(__cont.begin())
      |                                                 ~~~~~~~^~~~~
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp: In instantiation of 'xsimd::batch<T, A> xsimd::kernel::detail::batch_cast(const xsimd::batch<R, A>&, const xsimd::batch<T, A>&, xsimd::kernel::requires_arch<xsimd::generic>, with_slow_conversion) [with A = xsimd::neon; T_out = double; T_in = long long unsigned int; xsimd::kernel::requires_arch<xsimd::generic> = const xsimd::generic&]':
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:81:38   required from 'xsimd::batch<T, A> xsimd::kernel::batch_cast(const xsimd::batch<R, A>&, const xsimd::batch<T, A>&, requires_arch<xsimd::generic>) [with A = xsimd::neon; T_out = double; T_in = long long unsigned int; requires_arch<xsimd::generic> = const xsimd::generic&]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_api.hpp:233:37:   required from 'xsimd::batch<U, A> xsimd::batch_cast(const batch<T, A>&) [with T_out = double; T_in = long long unsigned int; A = neon]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_math/Math/chowdsp_RandomFloat.h:64:42:   required from here
/usr/include/c++/12/bits/range_access.h:95:5: note: candidate: 'template<class _Tp, unsigned int _Nm> constexpr _Tp* std::begin(_Tp (&)[_Nm])'
   95 |     begin(_Tp (&__arr)[_Nm]) noexcept
      |     ^~~~~
/usr/include/c++/12/bits/range_access.h:95:5: note:   template argument deduction/substitution failed:
In file included from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_json/third_party/nlohmann/json.hpp:150,
                 from /home/potato303/jc303_src/lib/chowdsp_utils-src/modules/common/chowdsp_json/chowdsp_json.h:24,
                 from /home/potato303/jc303_src/build/JC303_artefacts/JuceLibraryCode/JuceHeader.h:38:
/usr/include/c++/12/valarray:1217:5: note: candidate: 'template<class _Tp> _Tp* std::begin(valarray<_Tp>&)'
 1217 |     begin(valarray<_Tp>& __va) noexcept
      |     ^~~~~
/usr/include/c++/12/valarray:1217:5: note:   template argument deduction/substitution failed:
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:72:81 note:   mismatched types 'std::valarray<_Tp>' and 'double [0]'
   72 | :copy(std::begin(buffer_in), std::end(buffer_in), std::begin(buffer_out);
      |                                                   ~~~~~~~~~~^~~~~~~~~~~

/usr/include/c++/12/valarray:1228:5: note: candidate: 'template<class _Tp> const _Tp* std::begin(const valarray<_Tp>&)'
 1228 |     begin(const valarray<_Tp>& __va) noexcept
      |     ^~~~~
/usr/include/c++/12/valarray:1228:5: note:   template argument deduction/substitution failed:
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:72:81 note:   mismatched types 'const std::valarray<_Tp>' and 'double [0]'
   72 | :copy(std::begin(buffer_in), std::end(buffer_in), std::begin(buffer_out);
      |                                                   ~~~~~~~~~~^~~~~~~~~~~

/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp: In instantiation of 'xsimd::batch<T, A> xsimd::kernel::detail::batch_cast(const xsimd::batch<R, A>&, const xsimd::batch<T, A>&, xsimd::kernel::requires_arch<xsimd::generic>, with_slow_conversion) [with A = xsimd::neon; T_out = double; T_in = long long int; xsimd::kernel::requires_arch<xsimd::generic> = const xsimd::generic&]':
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:81:38   required from 'xsimd::batch<T, A> xsimd::kernel::batch_cast(const xsimd::batch<R, A>&, const xsimd::batch<T, A>&, requires_arch<xsimd::generic>) [with A = xsimd::neon; T_out = double; T_in = long long int; requires_arch<xsimd::generic> = const xsimd::generic&]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/xsimd_api.hpp:233:37:   required from 'xsimd::batch<U, A> xsimd::batch_cast(const batch<T, A>&) [with T_out = double; T_in = long long int; A = neon]'
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_math/Math/chowdsp_RandomFloat.h:94:42:   required from here
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:68:51 error: static assertion failed: compatible sizes
   68 |                 static_assert(batch_type_in::size == batch_type_out::size, "compatible sizes");
      |                                              ~~~~~^~~~~~~~~~~~~~~~~~~~~~~
/home/potato303/jc303_src/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/xsimd/include/xsimd/types/../arch/././generic/xsimd_generic_math.hpp:68:51 note: the comparison reduces to '(2 == 0)'
make[2]: *** [CMakeFiles/JC303.dir/build.make:349: CMakeFiles/JC303.dir/src/gui/midilab/Gui.cpp.o] Error 1
make[1]: *** [CMakeFiles/Makefile2:466: CMakeFiles/JC303.dir/all] Error 2
make: *** [Makefile:136: all] Error 2
potato303@raspberrypi:~ $ 
```

---

# 2026-05-28 / 2026-05-29

## SESSION 6 — First Successful Build ✅

_Antigravity (Google DeepMind) | Raspberry Pi OS Lite **64-bit** (Trixie) | potato303@192.168.1.84_

---

## The Breakthrough

After 5 failed sessions on 32-bit Raspberry Pi OS, the root cause was identified and eliminated by switching to **64-bit**.

**Root cause of all previous failures:**

ARMv7 (32-bit) NEON has no double-precision SIMD support. `xsimd::batch<double, neon>` does not exist on 32-bit ARM. The chowdsp_utils library (bundled with JC303) attempts to instantiate this type in at least two places:

1. `chowdsp_BBDFilterBank.h:78` — `xsimd::exp(batch<complex<float>, neon>)` internally needs `batch<double, neon>`
2. `chowdsp_RandomFloat.h:64` — `xsimd::batch_cast<double>(batch<uint64_t, neon>)`

These trigger `static_assert` failures at template instantiation time regardless of whether the code path is actually reached at runtime. Every file compiled as part of the JC303 JUCE target that includes `<JuceHeader.h>` pulls in the full chowdsp module chain and triggers the failure.

**Why 64-bit fixes it:**

On AArch64 (64-bit ARM), `xsimd::neon64` fully supports double-precision SIMD. `batch<double, neon64>` compiles cleanly. Zero source patches required.

---

## What was tried on 32-bit (all failed)

| Attempt | Why it failed |
|---|---|
| Swap xsimd 11.1.0 (Session 4/5 Grok) | Wrong module — RTNeural's xsimd, not chowdsp's |
| Headless GUI stub | Still includes `<JuceHeader.h>` which drags in all chowdsp |
| `-DCHOWDSP_NO_XSIMD=1` | Skips xsimd in `chowdsp_simd.h` but `chowdsp_SIMDAudioBlock.h` uses xsimd directly regardless |
| Patch `chowdsp_BBDFilterBank.h` | Fixed BBD, but `chowdsp_RandomFloat.h` is a separate failure |

---

## What succeeded

**Switched to Raspberry Pi OS Lite 64-bit (Trixie)**

- Flashed fresh SD card with RPi OS Lite 64-bit via Raspberry Pi Imager
- New SSH host key — old `known_hosts` entry cleared with `ssh-keygen -R 192.168.1.84`
- Configured passwordless sudo: `echo "potato303 ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/potato303-nopasswd`

**Script: `potato303_bootstrap.sh`** — single one-shot setup script:

1. Expands `dphys-swapfile` to 2GB (needed during compilation peak; idle at runtime)
2. `sudo apt-get install` — all JUCE + audio deps
3. `sudo apt install jalv` (note: needs patch, see below)
4. `git clone https://github.com/midilab/jc303.git` + `git submodule update --init --recursive`
5. Creates headless GUI stub at `src/gui/headless/`
6. `cmake` with `-DGUI=headless -DCMAKE_CXX_STANDARD=17 -DCMAKE_C_FLAGS="-O2 -march=native"`
7. `make -j2`
8. Copies `.lv2` bundle to `~/.lv2/`

**Build environment:**

| | |
|---|---|
| OS | Raspberry Pi OS Lite 64-bit (Trixie) |
| Architecture | `aarch64` |
| GCC | 14.2.0 (Debian 14.2.0-19) |
| cmake | 3.31.6 |
| Swap | 2GB via dphys-swapfile |
| Make parallelism | `-j2` |
| Build time | ~2h8m (22:51 → 00:59 CEST) |

**Result:** `JC303.lv2` installed to `~/.lv2/`

---

## jalv note

`sudo apt install jalv` installs from Trixie repos but the package needs a patch to work correctly. **User handles jalv build from source** (same as previous sessions — already a known procedure, not an issue).

jalv smoke test command:
```bash
jalv http://github.com/midilab/JC303
```

---

## Still to do

- [ ] Build jalv from source with patch (user handles)
- [ ] JACK autostart on boot
- [ ] MIDI routing (`a2jmidid`)
- [ ] Port/verify `engine.py`, `SYSTEM_BOOT.sh`, `mapping.yaml`, `tui.py`
- [ ] Test full chain end to end

---

_Antigravity (Google DeepMind) — antigravity-ide_