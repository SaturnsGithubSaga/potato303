#!/bin/bash
set -e
echo "=== Building JC-303 LV2 Plugin for i386 ==="
WORK_DIR="$HOME/jc303_src"
REPO_URL="https://github.com/midilab/jc303.git"
rm -rf "$WORK_DIR"
echo "Cloning JC-303..."
git clone "$REPO_URL" "$WORK_DIR"
cd "$WORK_DIR"
git submodule update --init --recursive
cd "$WORK_DIR/lib/chowdsp_utils-src/modules/dsp/chowdsp_simd/third_party/"
rm -rf xsimd
git clone --branch 11.1.0 --depth 1 https://github.com/xtensor-stack/xsimd.git
cd "$WORK_DIR"
mkdir -p build
cd build
echo "Configuring CMake for ARMv7 (NEON)..."
export CFLAGS="-O3 -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -ffast-math"
export CXXFLAGS="-O3 -march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=hard -ffast-math"
export LDFLAGS="-latomic"
cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS="$CFLAGS" \
    -DCMAKE_CXX_FLAGS="$CXXFLAGS" \
    -DCMAKE_SHARED_LINKER_FLAGS="$LDFLAGS" \
    -DCMAKE_MODULE_LINKER_FLAGS="$LDFLAGS" \
    -DCMAKE_EXE_LINKER_FLAGS="$LDFLAGS" \
    -DCMAKE_CXX_STANDARD=14 \
    -DJUCE_HEADLESS_PLUGIN_CLIENT=1 \
    -DJUCE_BUILD_EXTRAS=OFF
echo "Compiling project..."
make -j1
echo "Installing LV2 bundle..."
LV2_DIR="$HOME/.lv2"
mkdir -p "$LV2_DIR"
if [ -d "jc303.lv2" ]; then
    cp -r jc303.lv2 "$LV2_DIR/"
    echo "Success: jc303.lv2 installed to $LV2_DIR"
else
    BUNDLE=$(find . -maxdepth 2 -name "*.lv2" -type d | head -n 1)
    if [ -n "$BUNDLE" ]; then
        cp -r "$BUNDLE" "$LV2_DIR/"
        echo "Success: $(basename "$BUNDLE") installed to $LV2_DIR"
    else
        echo "Error: .lv2 bundle not found after compilation!"
        exit 1
    fi
fi
echo "=== Build and Installation Complete ==="
