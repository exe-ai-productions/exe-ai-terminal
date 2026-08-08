#!/bin/sh
# Puts the packaged service where the window build expects its sidecar.
#
# Tauri wants external binaries named with the machine's target triple —
# that is how one configuration can build on every system. Run after
# `pyinstaller deploy/exe-ai-terminal.spec`, from this folder.

set -e
hier="$(cd "$(dirname "$0")" && pwd)"
triple="$(rustc -vV | sed -n 's/^host: //p')"
mkdir -p "$hier/binaries"
cp "$hier/../dist/Exe AI Terminal" "$hier/binaries/exe-ai-terminal-$triple"
echo "Sidecar: binaries/exe-ai-terminal-$triple"
