#!/bin/bash
# cf-build — Build .cf or .cfe from XML sources
# Generalized from chronicon/scripts/build-release.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ROOT="$PWD"

SRC="" OUTF="" EXT="" TIMEOUT=300

while [[ $# -gt 0 ]]; do
  case $1 in
    --src)       SRC="$2"; shift 2;;
    --out)       OUTF="$2"; shift 2;;
    --extension) EXT="$2"; shift 2;;
    --timeout)   TIMEOUT="$2"; shift 2;;
    *) echo "Unknown: $1"; exit 1;;
  esac
done

V8=$(python3 -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR/../../_lib')
from v8_platform import resolve_v8path
print(resolve_v8path())
")
test -x "$V8" || { echo "Error: платформа 1С не найдена: $V8"; exit 1; }

# Auto-detect source dir
if [ -z "$SRC" ]; then
  for d in "src/cf" "src" "1c/standalone/src" "1c/extension/src"; do
    [ -f "$ROOT/$d/Configuration.xml" ] && { SRC="$ROOT/$d"; break; }
  done
fi
test -d "$SRC" || { echo "Error: исходники не найдены. Укажите --src"; exit 1; }

# Auto-detect output
if [ -z "$OUTF" ]; then
  PROJECT=$(basename "$ROOT")
  mkdir -p "$ROOT/build"
  if [ -n "$EXT" ]; then
    OUTF="$ROOT/build/$PROJECT.cfe"
  else
    OUTF="$ROOT/build/$PROJECT.cf"
  fi
fi
mkdir -p "$(dirname "$OUTF")"

guard() { perl -e "alarm $TIMEOUT; exec @ARGV" "$@"; }

BUILDIB="$ROOT/base/build-ib"
LOG="$ROOT/base/build.log"
rm -rf "$BUILDIB"; mkdir -p "$BUILDIB" "$(dirname "$LOG")"

echo "[1/4 create-ib]"
guard "$V8" CREATEINFOBASE File="$BUILDIB" /DisableStartupDialogs >/dev/null

echo "[2/4 load] $SRC"
if [ -n "$EXT" ]; then
    guard "$V8" DESIGNER /F"$BUILDIB" /LoadConfigFromFiles "$SRC" -Extension "$EXT" /UpdateDBCfg /DisableStartupDialogs /Out "$LOG" >/dev/null
else
    guard "$V8" DESIGNER /F"$BUILDIB" /LoadConfigFromFiles "$SRC" /UpdateDBCfg /DisableStartupDialogs /Out "$LOG" >/dev/null
fi

echo "[3/4 dump]"
if [ -n "$EXT" ]; then
    guard "$V8" DESIGNER /F"$BUILDIB" /DumpCfg "$OUTF" -Extension "$EXT" /DisableStartupDialogs /Out "$LOG" >/dev/null
else
    guard "$V8" DESIGNER /F"$BUILDIB" /DumpCfg "$OUTF" /DisableStartupDialogs /Out "$LOG" >/dev/null
fi

echo "[4/4 cleanup]"
rm -rf "$BUILDIB"

test -f "$OUTF" || { echo "Error: не собран: $OUTF"; cat "$LOG" 2>/dev/null; exit 1; }
SIZE=$(ls -lh "$OUTF" | awk '{print $5}')
echo "[ok] $OUTF ($SIZE)"
