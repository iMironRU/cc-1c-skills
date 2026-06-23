#!/bin/bash
# bsp-merge — Merge configuration with BSP (1C Standard Subsystems Library)
# Generalized from chronicon/scripts/integrate-bsp.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ROOT="$PWD"

BSP_CF="" SETTINGS="" SRC="" OUT="" TYPES_MAP=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --bsp-cf)    BSP_CF="$2"; shift 2;;
    --settings)  SETTINGS="$2"; shift 2;;
    --src)       SRC="$2"; shift 2;;
    --out)       OUT="$2"; shift 2;;
    --types-map) TYPES_MAP="$2"; shift 2;;
    *) echo "Unknown: $1"; exit 1;;
  esac
done

# Auto-detect v8path
V8=$(python3 -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR/../../_lib')
from v8_platform import resolve_v8path
print(resolve_v8path())
")
test -x "$V8" || { echo "Error: платформа 1С не найдена: $V8"; exit 1; }

# Auto-detect source dir
if [ -z "$SRC" ]; then
  for d in "src/cf" "src" "1c/standalone/src"; do
    [ -f "$ROOT/$d/Configuration.xml" ] && { SRC="$ROOT/$d"; break; }
  done
fi
test -d "$SRC" || { echo "Error: исходники не найдены. Укажите --src"; exit 1; }
test -n "$BSP_CF" || { echo "Error: укажите --bsp-cf <путь к CF БСП>"; exit 1; }
test -f "$BSP_CF" || { echo "Error: файл не найден: $BSP_CF"; exit 1; }

[ -z "$OUT" ] && OUT="$ROOT/base/bsp-merged-unpack"

IB="$ROOT/base/merge-test-ib"
LOG="$ROOT/base/bsp-merge.log"

echo "[1/8 clean] $IB и $OUT"
rm -rf "$IB" "$OUT"
mkdir -p "$IB" "$OUT" "$(dirname "$LOG")"

echo "[2/8 create-ib]"
"$V8" CREATEINFOBASE File="$IB" /DisableStartupDialogs >/dev/null

echo "[3/8 load-src] $SRC → ИБ"
"$V8" DESIGNER /F"$IB" /LoadConfigFromFiles "$SRC" /DisableStartupDialogs /Out "$LOG"

echo "[4/8 update-db-pre] UpdateDBCfg каркаса"
"$V8" DESIGNER /F"$IB" /UpdateDBCfg /DisableStartupDialogs /Out "$LOG"

MERGE_FLAGS="-EnableSupport -force"
[ -n "$SETTINGS" ] && MERGE_FLAGS="-Settings $SETTINGS $MERGE_FLAGS"

echo "[5/8 merge] MergeCfg БСП → ИБ (может занять 10-30 мин)"
"$V8" DESIGNER /F"$IB" /MergeCfg "$BSP_CF" $MERGE_FLAGS /DisableStartupDialogs /Out "$LOG"

echo "[6/8 dump-xml] DumpConfigToFiles → $OUT"
"$V8" DESIGNER /F"$IB" /DumpConfigToFiles "$OUT" /DisableStartupDialogs /Out "$LOG"

if [ -n "$TYPES_MAP" ] && [ -f "$TYPES_MAP" ]; then
    FILL_SCRIPT="$SCRIPT_DIR/../../bsp-fill-types/scripts/bsp-fill-types.py"
    if [ -f "$FILL_SCRIPT" ]; then
        echo "[7/8 post-merge] заполняем определяемые типы"
        python3 "$FILL_SCRIPT" --types-map "$TYPES_MAP" --unpack-dir "$OUT"
    else
        echo "[7/8 skip] скрипт bsp-fill-types.py не найден"
    fi
else
    echo "[7/8 skip] --types-map не указан"
fi

echo "[8/8 reload+update] LoadConfigFromFiles patched + final UpdateDBCfg"
"$V8" DESIGNER /F"$IB" /LoadConfigFromFiles "$OUT" /DisableStartupDialogs /Out "$LOG"
"$V8" DESIGNER /F"$IB" /UpdateDBCfg /DisableStartupDialogs /Out "$LOG"

echo ""
echo "[ok] слияние завершено"
echo "Merged ИБ:    $IB"
echo "Merged XML:   $OUT"
echo "Лог:          $LOG"
