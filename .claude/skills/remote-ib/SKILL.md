---
name: remote-ib
description: Деплой конфигурации и расширений на удалённую Windows ИБ через 1С Агент (AgentMode). Загружает CF/CFE и запускает UpdateDBCfg без GUI.
argument-hint: <deploy|deploy-ext|dump|update-db|status> [--cf <file>] [--ext <file>] [--out <file>]
allowed-tools:
  - Bash
  - Read
---

## Описание

Подключается к 1С Конфигуратору, запущенному в режиме `/AgentMode` на Windows-машине,
и выполняет операции без графического интерфейса: загрузка CF/CFE, UpdateDBCfg, выгрузка CF.

**Предварительные требования:**
1. На Windows запущен `start-1c-agent.ps1` (из `other/windows/`)
2. Сгенерирован SSH-ключ: `ssh-keygen -t ed25519 -f ~/.ssh/id_1c_agent`
3. Публичный ключ добавлен на Windows через пункт 6 меню скрипта
4. В `.v8-project.json` заполнен блок `"remote"`

## Команда

```bash
python3 .claude/skills/remote-ib/scripts/remote_ib.py <action> [параметры]
```

## Действия

| Действие | Описание |
|----------|----------|
| `status` | Проверить подключение к агенту |
| `deploy` | Загрузить CF → UpdateDBCfg (два шага) |
| `deploy-ext` | Загрузить расширение CFE |
| `update-db` | Только UpdateDBCfg (без загрузки CF) |
| `dump` | Выгрузить текущую конфигурацию в CF-файл |

## Параметры

| Параметр | Описание |
|----------|----------|
| `--cf <path>` | Локальный CF-файл для загрузки |
| `--ext <path>` | Локальный CFE-файл расширения |
| `--ext-name <name>` | Имя расширения (авто-определяется из имени файла) |
| `--out <path>` | Куда сохранить CF при dump (умолч: `build/remote-dump.cf`) |
| `--no-update-db` | При deploy — только загрузить CF без UpdateDBCfg |
| `--timeout <сек>` | Таймаут операции в секундах (умолч: 600) |

## Конфиг в .v8-project.json

```json
{
  "remote": {
    "host": "192.168.1.100",
    "agent_port": 1543,
    "user": "Администратор",
    "ssh_key": "~/.ssh/id_1c_agent"
  }
}
```

## Примеры

```bash
# Проверить соединение
python3 .claude/skills/remote-ib/scripts/remote_ib.py status

# Собрать и задеплоить (типичный цикл)
python3 .claude/skills/cf-build/scripts/cf_build.py
python3 .claude/skills/remote-ib/scripts/remote_ib.py deploy --cf build/project.cf

# Только UpdateDBCfg (CF уже загружена)
python3 .claude/skills/remote-ib/scripts/remote_ib.py update-db

# Загрузить расширение
python3 .claude/skills/remote-ib/scripts/remote_ib.py deploy-ext --ext build/MyExt.cfe

# Выгрузить текущую конфигурацию с Windows
python3 .claude/skills/remote-ib/scripts/remote_ib.py dump --out out/windows-cfg.cf
```

## Полный цикл разработки с тестированием

```bash
# 1. Собрать CF на Mac
python3 .claude/skills/cf-build/scripts/cf_build.py

# 2. Задеплоить на Windows тестовую ИБ
python3 .claude/skills/remote-ib/scripts/remote_ib.py deploy --cf build/project.cf

# 3. Запустить тесты через веб-клиент Windows ИБ
# (URL берётся из remote.web_url если задан, или http://<host>/<web_app_name>)
```

## Коды выхода

- `0` — успех
- `1` — ошибка конфигурации или подключения
- `2` — операция выполнена с ошибкой (агент вернул error)
