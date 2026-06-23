#!/usr/bin/env python3
"""Shared module for 1C:Enterprise platform detection on macOS/Linux/Windows.

Usage from skill scripts:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '_lib'))
    from v8_platform import resolve_v8path, find_project_root, load_v8_project
"""

import glob
import json
import os
import re
import sys


def find_project_root():
    """Walk up from CWD to find directory containing .v8-project.json."""
    d = os.getcwd()
    while True:
        if os.path.isfile(os.path.join(d, ".v8-project.json")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def load_v8_project():
    """Load .v8-project.json from the project root. Returns (data, path) or (None, None)."""
    root = find_project_root()
    if not root:
        return None, None
    pf = os.path.join(root, ".v8-project.json")
    try:
        with open(pf, encoding="utf-8-sig") as f:
            return json.load(f), pf
    except Exception:
        return None, None


def _find_project_v8path():
    """Read v8path from .v8-project.json."""
    data, _ = load_v8_project()
    if data:
        return data.get("v8path")
    return None


def _version_key(p):
    """Numeric sort key from version dir name (e.g. .../1cv8/8.3.24.1691/...)."""
    parts = p.replace("\\", "/").split("/")
    for part in parts:
        nums = re.findall(r"\d+", part)
        if len(nums) >= 3:
            return [int(x) for x in nums]
    return [0]


def _platform_candidates():
    """Return glob patterns for 1C platform binaries based on OS."""
    if sys.platform == "darwin":
        return [
            "/opt/1cv8/*/1cv8",
            "/opt/1cv8/*/ibcmd",
            "/opt/1C/v8.3/*/1cv8",
            "/opt/1C/v8.3/*/ibcmd",
            os.path.expanduser("~/Applications/1cv8/*/1cv8"),
        ]
    elif sys.platform == "linux":
        return [
            "/opt/1cv8/*/1cv8",
            "/opt/1cv8/*/ibcmd",
            "/opt/1C/v8.3/*/1cv8",
            "/opt/1C/v8.3/*/ibcmd",
        ]
    else:
        return [
            r"C:\Program Files\1cv8\*\bin\1cv8.exe",
            r"C:\Program Files (x86)\1cv8\*\bin\1cv8.exe",
        ]


def _exe_name(prefer_ibcmd=False):
    """Return the expected binary name for this OS."""
    if sys.platform == "win32":
        return "ibcmd.exe" if prefer_ibcmd else "1cv8.exe"
    return "ibcmd" if prefer_ibcmd else "1cv8"


def resolve_v8path(v8path=None, prefer_ibcmd=False, silent=False):
    """Resolve path to 1cv8 or ibcmd binary.

    Search order:
    1. Explicit v8path argument
    2. v8path from .v8-project.json
    3. Auto-detect from standard installation paths

    Args:
        v8path: Explicit path to bin directory or executable.
        prefer_ibcmd: If True, prefer ibcmd over 1cv8 when auto-detecting.
        silent: If True, return None instead of sys.exit on failure.

    Returns:
        Full path to the 1cv8/ibcmd executable.
    """
    if not v8path:
        v8path = _find_project_v8path()

    if not v8path:
        candidates = []
        for pattern in _platform_candidates():
            candidates.extend(glob.glob(pattern))
        if prefer_ibcmd:
            ibcmd_candidates = [c for c in candidates if "ibcmd" in os.path.basename(c).lower()]
            if ibcmd_candidates:
                candidates = ibcmd_candidates
            else:
                candidates = [c for c in candidates if "ibcmd" not in os.path.basename(c).lower()]
        else:
            candidates = [c for c in candidates if "ibcmd" not in os.path.basename(c).lower()]

        if candidates:
            v8path = max(candidates, key=_version_key)
            ver_parts = re.findall(r"\d+\.\d+\.\d+\.\d+", v8path)
            ver = ver_parts[0] if ver_parts else os.path.basename(os.path.dirname(v8path))
            print(f"Auto-selected platform {ver}: {v8path}")
        else:
            msg = f"Error: {_exe_name(prefer_ibcmd)} not found. Specify -V8Path or set v8path in .v8-project.json"
            if silent:
                return None
            print(msg, file=sys.stderr)
            sys.exit(1)

    exe = _exe_name(prefer_ibcmd)

    if os.path.isdir(v8path):
        candidate = os.path.join(v8path, exe)
        if os.path.isfile(candidate):
            v8path = candidate
        else:
            bins = [f for f in os.listdir(v8path) if f.lower() in ("1cv8", "1cv8.exe", "ibcmd", "ibcmd.exe")]
            if bins:
                v8path = os.path.join(v8path, bins[0])
            else:
                if silent:
                    return None
                print(f"Error: no 1C binaries found in {v8path}", file=sys.stderr)
                sys.exit(1)

    if not os.path.isfile(v8path):
        if silent:
            return None
        print(f"Error: {exe} not found at {v8path}", file=sys.stderr)
        sys.exit(1)

    return v8path


def detect_engine(v8path):
    """Detect engine type from binary path: 'ibcmd' or '1cv8'."""
    return "ibcmd" if "ibcmd" in os.path.basename(v8path).lower() else "1cv8"


def get_web_path():
    """Get Apache/httpd path from .v8-project.json or detect system installation."""
    data, _ = load_v8_project()
    if data and data.get("webPath"):
        return data["webPath"]

    if sys.platform == "darwin":
        candidates = [
            "/opt/homebrew/opt/httpd/bin/httpd",
            "/usr/local/opt/httpd/bin/httpd",
            "/usr/sbin/httpd",
        ]
        for c in candidates:
            if os.path.isfile(c):
                return os.path.dirname(os.path.dirname(c))
    elif sys.platform == "linux":
        for c in ["/usr/sbin/httpd", "/usr/sbin/apache2"]:
            if os.path.isfile(c):
                return os.path.dirname(os.path.dirname(c))

    return None


def get_ffmpeg_path():
    """Get ffmpeg path from .v8-project.json or detect from PATH."""
    data, _ = load_v8_project()
    if data and data.get("ffmpegPath"):
        return data["ffmpegPath"]

    import shutil as _shutil
    path = _shutil.which("ffmpeg")
    return path
