---
name: bsl-check
description: Синтаксический анализ кода 1С через BSL Language Server. Показывает ошибки, предупреждения и подсказки с номерами строк.
argument-hint: [--severity Error|Warning|Information|Hint] [--all] [--errors-only] [--src <path>]
allowed-tools:
  - Bash
  - Read
---

## Описание

Запускает BSL Language Server в режиме анализа (`analyze`) и выводит структурированный список диагностик с путями файлов и номерами строк.

Требует BSL Language Server. Установить: `/env-setup --bsl`

## Команда

```bash
python3 .claude/skills/bsl-check/scripts/bsl-check.py [параметры]
```

## Параметры

| Параметр | Описание |
|----------|----------|
| `--src <path>` | Каталог исходников (авто-поиск: `src/cf`, `src`, `1c/standalone/src`) |
| `--severity <уровень>` | Минимальный уровень: `Error`, `Warning` (умолч.), `Information`, `Hint` |
| `--all` | Показать всё включая Hint (то же что `--severity Hint`) |
| `--errors-only` | Только ошибки |
| `--show-ok` | Показать файлы без проблем |

## Уровни диагностик

| Иконка | Уровень | Описание |
|--------|---------|----------|
| `✗` | Error | Ошибка компиляции / синтаксиса |
| `△` | Warning | Предупреждение (подозрительный код) |
| `ℹ` | Information | Информационное замечание |
| `·` | Hint | Подсказка по стилю |

## Примеры

```bash
# Быстрая проверка — ошибки и предупреждения
python3 .claude/skills/bsl-check/scripts/bsl-check.py

# Только критические ошибки
python3 .claude/skills/bsl-check/scripts/bsl-check.py --errors-only

# Полный анализ со всеми подсказками
python3 .claude/skills/bsl-check/scripts/bsl-check.py --all

# Конкретный каталог
python3 .claude/skills/bsl-check/scripts/bsl-check.py --src src/cf
```

## Авто-определение BSL LS

Ищет в порядке приоритета:
1. `bsl-language-server` в PATH
2. `~/.local/bin/bsl-language-server`
3. VS Code расширение `1c-syntax.language-1c-bsl` (встроенный бинарник)
4. JAR в `~/.local/lib/bsl-language-server*-exec.jar` (запускается через `java`)

## Коды выхода

- `0` — нет ошибок (Warning/Hint не влияют)
- `1` — найдены Error-диагностики или BSL LS не найден
