#!/bin/bash
# =============================================================================
# build_jc303_headless.sh — Session 6
# =============================================================================
# Goal: headless JC303 LV2 for jalv on Raspberry Pi 3B (ARMv7, GCC-12, Trixie)
#
# Root cause (Session 5):
#   src/gui/midilab/Gui.cpp includes chowdsp_utils headers that use
#   xsimd::batch<double, neon> — ARMv7 NEON has NO 64-bit SIMD support.
#   This is a hard compile error that cannot be fixed with flags alone.
#
# Fix:
#   Create a headless GUI stub (src/gui/headless/) that provides the required
#   JC303Editor class and Gui.cpp without any chowdsp/xsimd includes.
#   Build with -DGUI=headless to use the stub instead of midilab.
# =============================================================================
set -e

echo "=== Building JC-303 LV2 (HEADLESS) for Raspberry Pi 3B ==="
echo "=== Using GCC-12, ARMv7 NEON float, headless GUI stub      ==="
echo ""

WORK_DIR="$HOME/jc303_src"
REPO_URL="https://github.com/midilab/jc303.git"

# --- 1. Clean and clone ---
rm -rf "$WORK_DIR"
echo "Cloning JC-303..."
git clone "$REPO_URL" "$WORK_DIR"
cd "$WORK_DIR"
git submodule update --init --recursive

# --- 2. Create headless GUI stub ---
echo "Creating headless GUI stub..."
HEADLESS_DIR="$WORK_DIR/src/gui/headless"
mkdir -p "$HEADLESS_DIR/resources"

# Headless Gui.h — minimal stub satisfying the JC303Editor contract
cat > "$HEADLESS_DIR/Gui.h" << 'HEADER_EOF'
#pragma once
// Headless GUI stub — no display, no chowdsp/xsimd includes
// Required by JC303.cpp: #include GUI_THEME_HEADER
#include <JuceHeader.h>
#include "../../JC303.h"

class JC303Editor : public juce::AudioProcessorEditor
{
public:
    explicit JC303Editor(JC303& p, juce::AudioProcessorValueTreeState&)
        : juce::AudioProcessorEditor(p) {}
    ~JC303Editor() override = default;
    void paint(juce::Graphics&) override {}
    void resized() override {}
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(JC303Editor)
};
HEADER_EOF

# Headless Gui.cpp — minimal implementation (no chowdsp includes)
cat > "$HEADLESS_DIR/Gui.cpp" << 'SOURCE_EOF'
// Headless GUI stub implementation
#include "Gui.h"
// Nothing else needed — all methods defined inline in Gui.h
SOURCE_EOF

# Headless CMakeLists.txt — matches the pattern used by midilab/amadeusp
# The midilab CMakeLists creates a BinaryData target for resources.
# Headless has no resources, so we create a minimal BinaryData placeholder.
cat > "$HEADLESS_DIR/CMakeLists.txt" << 'CMAKE_EOF'
# Headless GUI stub — no binary resources
# Create an empty BinaryData target to satisfy the main CMakeLists.txt
# which expects a BinaryData target from add_subdirectory(src/gui/${GUI})
juce_add_binary_data(BinaryData
    SOURCES
        resources/.gitkeep
)
CMAKE_EOF

# Create a placeholder file so juce_add_binary_data has at least one source
touch "$HEADLESS_DIR/resources/.gitkeep"

echo "Headless GUI stub created at $HEADLESS_DIR"

# --- 3. Patch src/CMakeLists.txt to use headless GUI ---
# The original line 28 is: gui/${GUI_THEME}/Gui.cpp
# With -DGUI=headless, GUI_THEME=headless, so the path becomes:
# gui/headless/Gui.cpp — which now exists!
echo "Verifying src/CMakeLists.txt will pick up headless Gui.cpp..."
grep "gui/\${GUI_THEME}/Gui.cpp" "$WORK_DIR/src/CMakeLists.txt" && \
    echo "  OK — src/CMakeLists.txt references gui/\${GUI_THEME}/Gui.cpp"

# --- 4. Build ---
mkdir -p build
cd build

echo ""
echo "Configuring CMake..."
echo "  Compiler: GCC-12"
echo "  Target:   ARMv7 + NEON (float only)"
echo "  GUI:      headless stub"
echo ""

# No -ffast-math: it enables aggressive FP opts that interact badly with xsimd.
# O2 instead of O3: safer on edge cases, still fast enough for RT audio.
# -latomic: required for std::atomic on ARMv7.
export CFLAGS="-O2 -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -mtune=cortex-a53"
# CHOWDSP_NO_XSIMD=1: documented chowdsp flag (chowdsp_simd.h:34) that skips xsimd.
# Without it, chowdsp_BBDFilterBank.h tries xsimd::exp(batch<complex<float>,neon>)
# which internally needs batch<double,neon> — unsupported on 32-bit ARM NEON.
export CXXFLAGS="$CFLAGS -DCHOWDSP_NO_XSIMD=1"
export LDFLAGS="-latomic"

cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=gcc-12 \
    -DCMAKE_CXX_COMPILER=g++-12 \
    -DCMAKE_C_FLAGS="$CFLAGS" \
    -DCMAKE_CXX_FLAGS="$CXXFLAGS" \
    -DCMAKE_SHARED_LINKER_FLAGS="$LDFLAGS" \
    -DCMAKE_MODULE_LINKER_FLAGS="$LDFLAGS" \
    -DCMAKE_EXE_LINKER_FLAGS="$LDFLAGS" \
    -DCMAKE_CXX_STANDARD=17 \
    -DJUCE_BUILD_EXTRAS=OFF \
    -DGUI=headless \
    -Wno-dev \
    2>&1

echo ""
echo "Compiling... (single core, will take ~60-90 min on Pi 3B)"
echo "Swapfile status:"
cat /proc/swaps || true
echo ""

make -j1 2>&1

# --- 5. Install ---
LV2_DIR="$HOME/.lv2"
mkdir -p "$LV2_DIR"

echo ""
echo "Searching for .lv2 bundle..."
BUNDLE=$(find . -maxdepth 4 -name "*.lv2" -type d 2>/dev/null | head -n 1)

if [ -n "$BUNDLE" ]; then
    cp -r "$BUNDLE" "$LV2_DIR/"
    BUNDLE_NAME=$(basename "$BUNDLE")
    echo ""
    echo "=== SUCCESS ==="
    echo "Installed: $BUNDLE_NAME -> $LV2_DIR/$BUNDLE_NAME"
    echo ""
    echo "Test with:"
    echo "  jalv http://github.com/midilab/JC303"
else
    echo ""
    echo "=== ERROR: No .lv2 bundle found ==="
    echo "The build may have failed. Check output above."
    echo ""
    echo "Installed files in build/:"
    find . -maxdepth 4 \( -name "*.lv2" -o -name "*.so" \) -type f 2>/dev/null | head -20
    exit 1
fi
