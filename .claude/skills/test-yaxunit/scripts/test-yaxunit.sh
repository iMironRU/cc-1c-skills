#!/bin/bash
# test-yaxunit — Run YAxUnit tests (headless, macOS)
# Generalized from chronicon/scripts/run-tests.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ROOT="$PWD"

SRC="" TESTS="" YAX="" EXT_NAME="tests" TIMEOUT=240

while [[ $# -gt 0 ]]; do
  case $1 in
    --src)      SRC="$2"; shift 2;;
    --tests)    TESTS="$2"; shift 2;;
    --yaxunit)  YAX="$2"; shift 2;;
    --ext-name) EXT_NAME="$2"; shift 2;;
    --timeout)  TIMEOUT="$2"; shift 2;;
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
  for d in "src/cf" "src" "1c/standalone/src"; do
    [ -f "$ROOT/$d/Configuration.xml" ] && { SRC="$ROOT/$d"; break; }
  done
fi
test -d "$SRC" || { echo "Error: исходники не найдены. Укажите --src"; exit 1; }

# Auto-detect tests dir
if [ -z "$TESTS" ]; then
  for d in "tests/src" "1c/standalone/tests/src" "src/tests"; do
    [ -d "$ROOT/$d" ] && { TESTS="$ROOT/$d"; break; }
  done
fi
test -d "$TESTS" || { echo "Error: тесты не найдены. Укажите --tests"; exit 1; }

# Auto-detect YAxUnit
[ -z "$YAX" ] && YAX="$ROOT/tools/yaxunit/YAxUnit.cfe"
test -f "$YAX" || { echo "Error: YAxUnit.cfe не найден: $YAX"; echo "Скачайте: https://github.com/bia-technologies/yaxunit/releases"; exit 1; }

DSM="$ROOT/tools/yaxunit/DisableSafeMode.epf"

guard() { perl -e "alarm $TIMEOUT; exec @ARGV" "$@"; }

IB="$ROOT/base/test-ib"
LOG="$ROOT/base/test-run.log"
rm -rf "$IB"; mkdir -p "$IB" "$(dirname "$LOG")"

echo "[1/5] создание ИБ"
guard "$V8" CREATEINFOBASE File="$IB" /DisableStartupDialogs >/dev/null

echo "[2/5] главная конфигурация: $SRC"
guard "$V8" DESIGNER /F"$IB" /LoadConfigFromFiles "$SRC" /UpdateDBCfg /DisableStartupDialogs /Out "$LOG" >/dev/null

echo "[3/5] расширение YAxUnit"
guard "$V8" DESIGNER /F"$IB" /LoadCfg "$YAX" -Extension YAxUnit /UpdateDBCfg /DisableStartupDialogs /Out "$LOG" >/dev/null

echo "[4/5] расширение $EXT_NAME: $TESTS"
guard "$V8" DESIGNER /F"$IB" /LoadConfigFromFiles "$TESTS" -Extension "$EXT_NAME" /UpdateDBCfg /DisableStartupDialogs /Out "$LOG" >/dev/null

echo "[5/5] снятие безопасного режима + прогон тестов"
mkdir -p ~/.1cv8/1C/1cv8/conf/
grep -q "DisableUnsafeActionProtection" ~/.1cv8/1C/1cv8/conf/conf.cfg 2>/dev/null \
  || echo "DisableUnsafeActionProtection=.*" >> ~/.1cv8/1C/1cv8/conf/conf.cfg
[ -f "$DSM" ] && guard "$V8" ENTERPRISE /F"$IB" /Execute "$DSM" /DisableStartupDialogs /DisableStartupMessages /Out "$LOG" >/dev/null

RP="$ROOT/base/yax-report.xml"; EX="$ROOT/base/yax-exit.txt"
rm -f "$RP" "$EX"
cat > "$ROOT/base/yax-config.json" <<JSON
{ "reportFormat": "jUnit", "reportPath": "$RP", "closeAfterTests": true,
  "showReport": false, "exitCode": "$EX",
  "filter": { "extensions": ["$EXT_NAME"] },
  "logging": { "console": false, "file": "$ROOT/base/yax.log", "level": "info" } }
JSON
guard "$V8" ENTERPRISE /F"$IB" /DisableSplash /DisableStartupDialogs /DisableStartupMessages \
  /RunModeManagedApplication /C "RunUnitTests=$ROOT/base/yax-config.json" >/dev/null || true

# Parse results
python3 - "$RP" <<'PY'
import sys, xml.etree.ElementTree as ET
try:
    r = ET.parse(sys.argv[1]).getroot()
except Exception as e:
    print(f"Error: не удалось разобрать отчёт: {e}", file=sys.stderr)
    sys.exit(1)
tot=f=e=sk=0
for s in r.findall(".//testsuite"):
    tot+=int(s.get("tests",0)); f+=int(s.get("failures",0)); e+=int(s.get("errors",0)); sk+=int(s.get("skipped",0) or 0)
    print(f"\nНабор {s.get('name')}: tests={s.get('tests')} failures={s.get('failures')} errors={s.get('errors')}")
    for tc in s.findall("testcase"):
        bad = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
        print(("   FAIL " if bad is not None else "   OK   ")+tc.get("name"))
        if bad is not None:
            print("        ->", (bad.get("message") or bad.text or "").strip()[:200])
print(f"\nИТОГО {tot}: OK={tot-f-e-sk} FAIL={f} ERROR={e} SKIP={sk}")
sys.exit(1 if (f or e) else 0)
PY
