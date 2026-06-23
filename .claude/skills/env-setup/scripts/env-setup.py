#!/usr/bin/env python3
"""env-setup — Bootstrap 1C development environment on macOS."""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '_lib'))
from v8_platform import resolve_v8path, find_project_root, load_v8_project


BSL_LS_VERSION = "1.0.1"
BSL_LS_REPO = "1c-syntax/bsl-language-server"


def check_command(cmd):
    """Check if a command is available."""
    return shutil.which(cmd) is not None


def check_python_module(module):
    """Check if a Python module is importable."""
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def get_v8_status():
    """Check 1C platform installation."""
    v8 = resolve_v8path(silent=True)
    if v8:
        return True, v8
    return False, None


def get_bsl_ls_status():
    """Check BSL Language Server installation."""
    if check_command("bsl-language-server"):
        return True, shutil.which("bsl-language-server")

    local_path = os.path.expanduser("~/.local/bin/bsl-language-server")
    if os.path.isfile(local_path):
        return True, local_path

    # VS Code extension native binary (1c-syntax.language-1c-bsl)
    vsc_pattern = os.path.expanduser(
        "~/Library/Application Support/Code/User/globalStorage/"
        "1c-syntax.language-1c-bsl/bsl-language-server/v*/"
        "bsl-language-server.app/Contents/MacOS/bsl-language-server"
    )
    vsc_matches = sorted(glob.glob(vsc_pattern))
    if vsc_matches:
        return True, vsc_matches[-1]

    jar_patterns = [
        os.path.expanduser("~/.local/lib/bsl-language-server*-exec.jar"),
        os.path.expanduser("~/.local/share/bsl-language-server/bsl-language-server*-exec.jar"),
    ]
    for pattern in jar_patterns:
        jars = sorted(glob.glob(pattern))
        if jars:
            return True, jars[-1]

    return False, None


def get_java_status():
    """Check Java 17+ availability."""
    if not check_command("java"):
        return False, None
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True)
        output = result.stderr + result.stdout
        import re
        match = re.search(r'"(\d+)', output)
        if match:
            ver = int(match.group(1))
            if ver >= 17:
                return True, f"Java {ver}"
            return False, f"Java {ver} (need 17+)"
    except Exception:
        pass
    return False, None


def print_status():
    """Print environment status report."""
    print("=" * 50)
    print("  Окружение разработки 1С на macOS")
    print("=" * 50)
    print()

    checks = []

    # 1C Platform
    ok, detail = get_v8_status()
    checks.append(("Платформа 1С", ok, detail or "не найдена"))

    # Java
    ok, detail = get_java_status()
    checks.append(("Java 17+", ok, detail or "не найдена"))

    # BSL Language Server
    ok, detail = get_bsl_ls_status()
    checks.append(("BSL Language Server", ok, detail or "не установлен"))

    # Python deps
    for mod, name in [("lxml", "lxml (XML DOM)"), ("psutil", "psutil (процессы)")]:
        ok = check_python_module(mod)
        checks.append((name, ok, "установлен" if ok else "pip3 install " + mod))

    # Node.js
    ok = check_command("node")
    if ok:
        try:
            ver = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
            checks.append(("Node.js", True, ver))
        except Exception:
            checks.append(("Node.js", True, ""))
    else:
        checks.append(("Node.js 18+", False, "не найден (нужен для /web-test)"))

    # Homebrew
    ok = check_command("brew")
    checks.append(("Homebrew", ok, "установлен" if ok else "не найден"))

    # .v8-project.json
    root = find_project_root()
    if root:
        checks.append((".v8-project.json", True, root))
    else:
        checks.append((".v8-project.json", False, "не найден"))

    max_name = max(len(c[0]) for c in checks)
    for name, ok, detail in checks:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name:<{max_name}}  {detail}")

    print()
    all_ok = all(c[1] for c in checks)
    if all_ok:
        print("  Всё готово к работе!")
    else:
        print("  Есть недостающие компоненты. Запустите: /env-setup --install")
    print()
    return all_ok


def install_bsl_ls():
    """Download and install BSL Language Server."""
    ok, path = get_bsl_ls_status()
    if ok:
        print(f"BSL Language Server уже установлен: {path}")
        return True

    ok, detail = get_java_status()
    if not ok:
        print("Error: Java 17+ необходима для BSL Language Server", file=sys.stderr)
        if check_command("brew"):
            print("  Установите: brew install openjdk@17")
        else:
            print("  Установите JDK 17: https://adoptium.net/")
        return False

    lib_dir = os.path.expanduser("~/.local/lib")
    bin_dir = os.path.expanduser("~/.local/bin")
    os.makedirs(lib_dir, exist_ok=True)
    os.makedirs(bin_dir, exist_ok=True)

    jar_name = f"bsl-language-server-{BSL_LS_VERSION}-exec.jar"
    jar_path = os.path.join(lib_dir, jar_name)

    url = f"https://github.com/{BSL_LS_REPO}/releases/download/v{BSL_LS_VERSION}/{jar_name}"
    print(f"Скачиваю BSL Language Server v{BSL_LS_VERSION}...")
    print(f"  URL: {url}")

    try:
        urllib.request.urlretrieve(url, jar_path)
    except Exception as e:
        print(f"Error: не удалось скачать: {e}", file=sys.stderr)
        return False

    wrapper = os.path.join(bin_dir, "bsl-language-server")
    with open(wrapper, "w") as f:
        f.write(f'#!/bin/sh\nexec java -jar "{jar_path}" "$@"\n')
    os.chmod(wrapper, 0o755)

    print(f"Установлен: {wrapper}")
    print(f"  JAR: {jar_path}")

    shell_rc = os.path.expanduser("~/.zshrc")
    with open(shell_rc, "r") as f:
        rc_content = f.read()
    if "/.local/bin" not in rc_content:
        print()
        print(f'  Добавьте в {shell_rc}:')
        print(f'  export PATH="$HOME/.local/bin:$PATH"')

    return True


def install_python_deps():
    """Install Python dependencies via pip."""
    missing = []
    for mod in ["lxml", "psutil"]:
        if not check_python_module(mod):
            missing.append(mod)

    if not missing:
        print("Python-зависимости уже установлены.")
        return True

    print(f"Устанавливаю: {', '.join(missing)}")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--user"] + missing,
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("Установлено успешно.")
        return True
    else:
        print(f"Error: pip install failed\n{result.stderr}", file=sys.stderr)
        return False


def init_project():
    """Create .v8-project.json template in current directory."""
    target = os.path.join(os.getcwd(), ".v8-project.json")
    if os.path.exists(target):
        print(f"Файл уже существует: {target}")
        return

    v8, _ = get_v8_status()
    v8path = ""
    if v8:
        v8_resolved = resolve_v8path(silent=True)
        if v8_resolved:
            v8path = os.path.dirname(v8_resolved)

    template = {
        "v8path": v8path,
        "databases": [
            {
                "id": "dev",
                "alias": "dev",
                "name": "Разработка",
                "path": os.path.expanduser("~/bases/dev"),
                "configSrc": "src/cf",
                "default": True,
            }
        ],
    }

    with open(target, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    print(f"Создан: {target}")


def main():
    parser = argparse.ArgumentParser(description="Setup 1C dev environment on macOS")
    parser.add_argument("--check", action="store_true", help="Only check status")
    parser.add_argument("--install", action="store_true", help="Install all missing components")
    parser.add_argument("--bsl", action="store_true", help="Install BSL Language Server only")
    parser.add_argument("--deps", action="store_true", help="Install Python dependencies only")
    parser.add_argument("--init-project", action="store_true", help="Create .v8-project.json template")
    args = parser.parse_args()

    if args.init_project:
        init_project()
        return

    if args.bsl:
        success = install_bsl_ls()
        sys.exit(0 if success else 1)

    if args.deps:
        success = install_python_deps()
        sys.exit(0 if success else 1)

    all_ok = print_status()

    if args.install and not all_ok:
        print("-" * 50)
        print("  Устанавливаю недостающие компоненты...")
        print()
        install_python_deps()
        install_bsl_ls()
        print()
        print_status()
    elif args.check:
        sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
