#!/bin/bash
# sync.sh - Sync files between local workspace and remote potato303 server

REMOTE="potato303:~/"
LOCAL="$(cd "$(dirname "$0")" && pwd)/"

EXCLUDES=(
    --exclude=".git"
    --exclude=".DS_Store"
    --exclude=".local"
    --exclude=".antigravity-ide-server"
    --exclude=".bash_history"
    --exclude=".cloud-locale-test.skip"
    --exclude="sync.sh"
    --exclude="jc303_src/build"
    --exclude="jc303_src/lib"
    --exclude="jalv-1.6.8"
    --exclude="jalv-1.6.8.tar.xz"
    --exclude="outputjc303compile.md"
)

usage() {
    echo "Usage: $0 {push|pull|watch}"
    echo "  push   - Sync local changes to remote potato303"
    echo "  pull   - Sync remote changes to local workspace"
    echo "  watch  - Watch local files and automatically push changes"
    exit 1
}

push() {
    echo "Syncing local changes to remote potato303..."
    rsync -avz "${EXCLUDES[@]}" "$LOCAL" "$REMOTE"
}

pull() {
    echo "Syncing remote changes to local workspace..."
    rsync -avz "${EXCLUDES[@]}" "$REMOTE" "$LOCAL"
}

watch() {
    echo "Watching local workspace for changes (requires fswatch or entr)..."
    if command -v fswatch >/dev/null 2>&1; then
        echo "Using fswatch to monitor changes..."
        fswatch -o "$LOCAL" | while read -r f; do
            push
        done
    elif command -v entr >/dev/null 2>&1; then
        echo "Using entr to monitor changes..."
        find "$LOCAL" -type f "${EXCLUDES[@]}" | entr -r "$0" push
    else
        echo "Neither fswatch nor entr is installed."
        echo "Please install fswatch (e.g., 'brew install fswatch') to use the watch mode."
        echo "For now, running a simple 5-second polling loop..."
        while true; do
            push
            sleep 5
        done
    fi
}

case "$1" in
    push)
        push
        ;;
    pull)
        pull
        ;;
    watch)
        watch
        ;;
    *)
        usage
        ;;
esac
