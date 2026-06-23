#!/usr/bin/env python3
"""Syntax analysis of 1C source code via BSL Language Server."""

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '_lib'))
from v8_platform import find_project_root

SEVERITY_ORDER = {"Error": 0, "Warning": 1, "Information": 2, "Hint": 3}
SEVERITY_ICON = {"Error": "✗", "Warning": "△", "Information": "ℹ", "Hint": "·"}


def find_bsl_ls():
    """Locate BSL Language Server binary."""
    import shutil

    # 1. PATH
    if shutil.which("bsl-language-server"):
        return shutil.which("bsl-language-server")

    # 2. ~/.local/bin wrapper
    local = os.path.expanduser("~/.local/bin/bsl-language-server")
    if os.path.isfile(local) and os.access(local, os.X_OK):
        return local

    # 3. VS Code extension native binary (installed by 1C BSL extension)
    vsc_pattern = os.path.expanduser(
        "~/Library/Application Support/Code/User/globalStorage/"
        "1c-syntax.language-1c-bsl/bsl-language-server/v*/bsl-language-server.app"
        "/Contents/MacOS/bsl-language-server"
    )
    matches = sorted(glob.glob(vsc_pattern))
    if matches:
        return matches[-1]  # newest version

    # 4. JAR in ~/.local/lib — wrap with java
    jar_pattern = os.path.expanduser("~/.local/lib/bsl-language-server*-exec.jar")
    jars = sorted(glob.glob(jar_pattern))
    if jars:
        return ("jar", jars[-1])  # tuple signals jar mode

    return None


def run_analysis(bsl, src_dir, out_dir):
    cmd_base = [bsl, "analyze", "-s", str(src_dir), "-o", str(out_dir), "-r", "json", "-q"]

    if isinstance(bsl, tuple) and bsl[0] == "jar":
        cmd_base = ["java", "-jar", bsl[1],
                    "analyze", "-s", str(src_dir), "-o", str(out_dir), "-r", "json", "-q"]

    result = subprocess.run(cmd_base, capture_output=True, text=True)
    return result.returncode, result.stderr


def parse_report(out_dir, src_dir, min_severity, show_files_ok):
    report_path = Path(out_dir) / "bsl-json.json"
    if not report_path.exists():
        print("Error: отчёт не создан", file=sys.stderr)
        return False

    data = json.loads(report_path.read_text(encoding="utf-8"))
    fileinfos = data.get("fileinfos", [])
    src_str = str(src_dir)

    threshold = SEVERITY_ORDER.get(min_severity, 3)

    counts = {"Error": 0, "Warning": 0, "Information": 0, "Hint": 0}
    has_printed = False

    for fi in sorted(fileinfos, key=lambda x: x.get("path", "")):
        raw_path = fi.get("path", "")
        # file:///abs/path → abs/path, then make relative
        abs_path = unquote(raw_path.replace("file://", ""))
        try:
            rel = os.path.relpath(abs_path, src_str)
        except ValueError:
            rel = abs_path

        diags = [d for d in fi.get("diagnostics", [])
                 if SEVERITY_ORDER.get(d.get("severity", "Hint"), 3) <= threshold]

        if not diags:
            if show_files_ok:
                print(f"  OK  {rel}")
            continue

        # Group by severity for sorting
        diags.sort(key=lambda d: (
            SEVERITY_ORDER.get(d.get("severity", "Hint"), 3),
            d.get("range", {}).get("start", {}).get("line", 0),
        ))

        print(f"\n{rel}")
        for d in diags:
            sev = d.get("severity", "Hint")
            counts[sev] = counts.get(sev, 0) + 1
            icon = SEVERITY_ICON.get(sev, "?")
            line = d.get("range", {}).get("start", {}).get("line", 0) + 1
            col = d.get("range", {}).get("start", {}).get("character", 0) + 1
            code = d.get("code", "")
            msg = d.get("message", "")
            print(f"  {icon} {line}:{col}  [{code}]  {msg}")
        has_printed = True

    print()
    parts = []
    for sev in ("Error", "Warning", "Information", "Hint"):
        n = counts[sev]
        if n:
            parts.append(f"{SEVERITY_ICON[sev]} {sev}: {n}")
    total = sum(counts.values())
    if total == 0:
        print("[ok] проблем не найдено")
        return True
    print("[итого] " + "  ".join(parts))
    return counts["Error"] == 0


def find_src_dir():
    root = find_project_root() or os.getcwd()
    for d in ["src/cf", "src", "1c/standalone/src", "1c/extension/src"]:
        p = os.path.join(root, d)
        if os.path.isdir(p) and any(
            f.endswith((".bsl", ".os", ".xml"))
            for _, _, files in os.walk(p)
            for f in files
        ):
            return Path(p)
    return None


def main():
    p = argparse.ArgumentParser(description="BSL Language Server analysis")
    p.add_argument("--src", default="", help="Source directory (auto-detected if omitted)")
    p.add_argument("--severity", default="Warning",
                   choices=["Error", "Warning", "Information", "Hint"],
                   help="Minimum severity to show (default: Warning)")
    p.add_argument("--all", dest="show_all", action="store_true",
                   help="Show all including Hints (same as --severity Hint)")
    p.add_argument("--errors-only", action="store_true",
                   help="Show only Errors")
    p.add_argument("--show-ok", action="store_true",
                   help="Show files with no issues")
    args = p.parse_args()

    if args.show_all:
        args.severity = "Hint"
    if args.errors_only:
        args.severity = "Error"

    bsl = find_bsl_ls()
    if not bsl:
        print("Error: BSL Language Server не найден.", file=sys.stderr)
        print("Установите: /env-setup --bsl", file=sys.stderr)
        sys.exit(1)
    bsl_display = bsl if isinstance(bsl, str) else f"java -jar {bsl[1]}"
    print(f"BSL LS: {bsl_display}")

    src_dir = Path(args.src) if args.src else find_src_dir()
    if not src_dir:
        print("Error: директория исходников не найдена. Укажите --src", file=sys.stderr)
        sys.exit(1)
    print(f"Анализ: {src_dir}")
    print()

    with tempfile.TemporaryDirectory() as out_dir:
        rc, stderr = run_analysis(bsl, src_dir, out_dir)
        # BSL LS exits 0 even with diagnostics; stderr has only JVM warnings
        ok = parse_report(out_dir, src_dir, args.severity, args.show_ok)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
