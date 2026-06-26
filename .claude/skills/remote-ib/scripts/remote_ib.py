#!/usr/bin/env python3
"""
remote_ib.py — деплой конфигурации на удалённую Windows ИБ через 1С AgentMode.

Использует системные ssh/sftp (без сторонних зависимостей).
Конфиг читает из .v8-project.json блок "remote".
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def find_project_root() -> Path:
    cur = Path.cwd()
    for p in [cur, *cur.parents]:
        if (p / '.v8-project.json').exists():
            return p
    return cur


def load_remote_cfg() -> dict:
    root = find_project_root()
    cfg_file = root / '.v8-project.json'
    if not cfg_file.exists():
        die(f"Файл .v8-project.json не найден (искал от {root})\n"
            "Создай его через: python3 .claude/skills/env-setup/scripts/env_setup.py")

    with open(cfg_file, encoding='utf-8') as f:
        full = json.load(f)

    remote = full.get('remote')
    if not remote:
        die("В .v8-project.json нет блока \"remote\".\n\n"
            "Добавь:\n"
            '  "remote": {\n'
            '    "host": "192.168.1.100",\n'
            '    "agent_port": 1543,\n'
            '    "user": "Администратор",\n'
            '    "ssh_key": "~/.ssh/id_1c_agent"\n'
            '  }')

    for field in ('host', 'agent_port', 'user', 'ssh_key'):
        if not remote.get(field):
            die(f"Не заполнено поле remote.{field} в .v8-project.json")

    remote['ssh_key'] = os.path.expanduser(remote['ssh_key'])
    remote['_root'] = root
    return remote


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def die(msg: str, code: int = 1) -> None:
    print(f"\n[!!] {msg}", file=sys.stderr)
    sys.exit(code)


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def info(msg: str) -> None:
    print(f"[  ] {msg}")


def err(msg: str) -> None:
    print(f"[!!] {msg}", file=sys.stderr)


def ssh_base_args(cfg: dict) -> list:
    return [
        'ssh',
        '-i', cfg['ssh_key'],
        '-p', str(cfg['agent_port']),
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'BatchMode=yes',
        '-o', 'ConnectTimeout=15',
        f"{cfg['user']}@{cfg['host']}",
    ]


def sftp_base_args(cfg: dict) -> list:
    return [
        'sftp',
        '-i', cfg['ssh_key'],
        '-P', str(cfg['agent_port']),
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'BatchMode=yes',
        '-o', 'ConnectTimeout=15',
        '-b', '-',
        f"{cfg['user']}@{cfg['host']}",
    ]


# ---------------------------------------------------------------------------
# Agent protocol
# ---------------------------------------------------------------------------

def parse_agent_output(raw: str) -> list[dict]:
    """Парсит JSON-массивы из вывода 1С агента."""
    messages = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            try:
                msgs = json.loads(line)
                if isinstance(msgs, list):
                    messages.extend(msgs)
            except json.JSONDecodeError:
                pass
        elif line.startswith('{') and line.endswith('}'):
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return messages


def print_agent_messages(messages: list[dict]) -> bool:
    """Выводит сообщения агента. Возвращает True если были ошибки."""
    has_error = False
    for m in messages:
        mtype = m.get('type', '')
        text = m.get('text') or m.get('message') or str(m)
        level = m.get('level', '')

        if mtype == 'error' or level == 'error':
            err(f"  {text}")
            has_error = True
        elif mtype == 'progress':
            pct = m.get('progress', '')
            info(f"  {text} {pct}%".rstrip())
        elif text:
            info(f"  {text}")
    return has_error


def run_agent(cfg: dict, commands: list[str], timeout: int = 600) -> tuple[bool, str]:
    """
    Отправляет команды агенту, возвращает (success, raw_output).
    """
    setup = [
        'options set --output-format=json',
        'options set --notify-progress=yes',
    ]
    all_cmds = setup + commands + ['exit']
    stdin_data = '\n'.join(all_cmds) + '\n'

    ssh_args = ssh_base_args(cfg)

    try:
        result = subprocess.run(
            ssh_args,
            input=stdin_data.encode('utf-8'),
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        die(f"Таймаут {timeout}с при выполнении команд агента")
    except FileNotFoundError:
        die("ssh не найден. Установи OpenSSH: brew install openssh")

    stdout = result.stdout.decode('utf-8', errors='replace')
    stderr = result.stderr.decode('utf-8', errors='replace')

    if result.returncode != 0 and not stdout.strip():
        err(f"SSH ошибка (код {result.returncode}):")
        if stderr.strip():
            err(f"  {stderr.strip()}")
        return False, stdout

    return True, stdout


# ---------------------------------------------------------------------------
# File transfer
# ---------------------------------------------------------------------------

def upload_file(cfg: dict, local_path: Path, remote_name: str, timeout: int = 120) -> bool:
    """
    Загружает файл на агент через SFTP.
    remote_name — путь относительно AgentBaseDir агента (напр. 'build/proj.cf').
    """
    info(f"Загрузка {local_path.name} → агент:{remote_name}")

    batch = f"put \"{local_path}\" \"{remote_name}\"\n"
    sftp_args = sftp_base_args(cfg)

    try:
        result = subprocess.run(
            sftp_args,
            input=batch.encode('utf-8'),
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        err(f"Таймаут {timeout}с при загрузке файла")
        return False
    except FileNotFoundError:
        err("sftp не найден. Установи OpenSSH: brew install openssh")
        return False

    if result.returncode != 0:
        stderr = result.stderr.decode('utf-8', errors='replace')
        err(f"SFTP ошибка: {stderr.strip()}")
        # SFTP к 1С агенту может не работать — предлагаем обходной путь
        info("SFTP не поддерживается агентом. Попробуй скопировать файл вручную на Windows")
        info("или настрой Windows OpenSSH на порту 22 для передачи файлов.")
        return False

    ok(f"Файл загружен: {remote_name}")
    return True


def download_file(cfg: dict, remote_name: str, local_path: Path, timeout: int = 120) -> bool:
    """Скачивает файл с агента через SFTP."""
    batch = f"get \"{remote_name}\" \"{local_path}\"\n"
    sftp_args = sftp_base_args(cfg)

    try:
        result = subprocess.run(
            sftp_args,
            input=batch.encode('utf-8'),
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        err(f"Таймаут {timeout}с при скачивании файла")
        return False
    except FileNotFoundError:
        err("sftp не найден.")
        return False

    if result.returncode != 0:
        stderr = result.stderr.decode('utf-8', errors='replace')
        err(f"SFTP ошибка при скачивании: {stderr.strip()}")
        return False

    ok(f"Файл скачан: {local_path}")
    return True


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def action_status(cfg: dict, args) -> int:
    info(f"Проверка соединения: {cfg['user']}@{cfg['host']}:{cfg['agent_port']}")
    info(f"SSH-ключ: {cfg['ssh_key']}")

    if not Path(cfg['ssh_key']).exists():
        err(f"SSH-ключ не найден: {cfg['ssh_key']}")
        info("Создай ключ: ssh-keygen -t ed25519 -f ~/.ssh/id_1c_agent")
        return 1

    ok_conn, raw = run_agent(cfg, ['version'], timeout=30)
    if not ok_conn:
        return 1

    messages = parse_agent_output(raw)
    if not messages and raw.strip():
        # Агент ответил но не JSON — показываем raw
        info(f"Ответ агента: {raw.strip()[:200]}")
    else:
        for m in messages:
            text = m.get('text') or str(m)
            info(f"  {text}")

    ok(f"Агент доступен: {cfg['user']}@{cfg['host']}:{cfg['agent_port']}")

    if cfg.get('web_url'):
        info(f"Web URL: {cfg['web_url']}")

    return 0


def action_deploy(cfg: dict, args) -> int:
    cf_path = Path(args.cf) if args.cf else None
    if not cf_path:
        # Попробуем найти CF в build/
        root = cfg['_root']
        candidates = list((root / 'build').glob('*.cf')) if (root / 'build').exists() else []
        if candidates:
            cf_path = max(candidates, key=lambda p: p.stat().st_mtime)
            info(f"CF не указан, использую: {cf_path.relative_to(root)}")
        else:
            die("Укажи CF-файл: --cf build/project.cf")

    if not cf_path.exists():
        die(f"CF-файл не найден: {cf_path}")

    info(f"Деплой: {cf_path.name} → {cfg['user']}@{cfg['host']}")
    print()

    # 1. Загрузить файл на агент
    remote_cf = f"build/{cf_path.name}"
    if not upload_file(cfg, cf_path, remote_cf, timeout=args.timeout):
        return 1

    print()

    # 2. Загрузить конфигурацию
    info("Загружаю конфигурацию (config load-cfg)...")
    cmds = [f'config load-cfg "../{remote_cf}"']

    if not args.no_update_db:
        cmds.append('config update-db --warnings-as-errors no')

    ok_conn, raw = run_agent(cfg, cmds, timeout=args.timeout)
    if not ok_conn:
        return 1

    messages = parse_agent_output(raw)
    has_error = print_agent_messages(messages)

    if has_error:
        return 2

    print()
    ok("Конфигурация загружена")
    if not args.no_update_db:
        ok("UpdateDBCfg выполнен")

    if cfg.get('web_url'):
        info(f"Тестовая база: {cfg['web_url']}")

    return 0


def action_deploy_ext(cfg: dict, args) -> int:
    ext_path = Path(args.ext) if args.ext else None
    if not ext_path:
        root = cfg['_root']
        candidates = list((root / 'build').glob('*.cfe')) if (root / 'build').exists() else []
        if candidates:
            ext_path = max(candidates, key=lambda p: p.stat().st_mtime)
            info(f"CFE не указан, использую: {ext_path.relative_to(root)}")
        else:
            die("Укажи CFE-файл: --ext build/MyExt.cfe")

    if not ext_path.exists():
        die(f"CFE-файл не найден: {ext_path}")

    # Имя расширения из имени файла
    ext_name = args.ext_name or ext_path.stem
    info(f"Расширение: {ext_name} ({ext_path.name})")
    print()

    remote_ext = f"build/{ext_path.name}"
    if not upload_file(cfg, ext_path, remote_ext, timeout=args.timeout):
        return 1

    print()
    info(f"Загружаю расширение {ext_name}...")
    cmds = [f'config load-ext "../{remote_ext}" --name "{ext_name}"']

    ok_conn, raw = run_agent(cfg, cmds, timeout=args.timeout)
    if not ok_conn:
        return 1

    messages = parse_agent_output(raw)
    has_error = print_agent_messages(messages)

    if has_error:
        return 2

    ok(f"Расширение {ext_name} загружено")
    return 0


def action_update_db(cfg: dict, args) -> int:
    info("UpdateDBCfg...")
    ok_conn, raw = run_agent(cfg, ['config update-db --warnings-as-errors no'], timeout=args.timeout)
    if not ok_conn:
        return 1

    messages = parse_agent_output(raw)
    has_error = print_agent_messages(messages)

    if has_error:
        return 2

    ok("UpdateDBCfg выполнен")
    return 0


def action_dump(cfg: dict, args) -> int:
    out_path = Path(args.out) if args.out else cfg['_root'] / 'build' / 'remote-dump.cf'
    out_path.parent.mkdir(parents=True, exist_ok=True)

    remote_out = 'out/dump.cf'
    info(f"Выгружаю конфигурацию с агента → {out_path}")

    ok_conn, raw = run_agent(cfg, [f'config dump-cfg "../{remote_out}"'], timeout=args.timeout)
    if not ok_conn:
        return 1

    messages = parse_agent_output(raw)
    has_error = print_agent_messages(messages)
    if has_error:
        return 2

    print()
    if not download_file(cfg, remote_out, out_path, timeout=args.timeout):
        return 1

    ok(f"Конфигурация выгружена: {out_path}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Деплой на удалённую Windows ИБ через 1С AgentMode'
    )
    parser.add_argument('action',
                        choices=['status', 'deploy', 'deploy-ext', 'update-db', 'dump'],
                        help='Действие')
    parser.add_argument('--cf', metavar='PATH', help='CF-файл для загрузки')
    parser.add_argument('--ext', metavar='PATH', help='CFE-файл расширения')
    parser.add_argument('--ext-name', metavar='NAME', help='Имя расширения')
    parser.add_argument('--out', metavar='PATH', help='Куда сохранить CF при dump')
    parser.add_argument('--no-update-db', action='store_true',
                        help='При deploy — не запускать UpdateDBCfg')
    parser.add_argument('--timeout', type=int, default=600,
                        help='Таймаут операции в секундах (умолч: 600)')

    args = parser.parse_args()

    cfg = load_remote_cfg()

    print()
    print(f"remote-ib: {cfg['user']}@{cfg['host']}:{cfg['agent_port']}")
    print()

    actions = {
        'status':      action_status,
        'deploy':      action_deploy,
        'deploy-ext':  action_deploy_ext,
        'update-db':   action_update_db,
        'dump':        action_dump,
    }

    rc = actions[args.action](cfg, args)
    sys.exit(rc)


if __name__ == '__main__':
    main()
