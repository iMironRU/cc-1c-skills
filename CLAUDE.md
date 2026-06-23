# 1C2Claude — центральный репозиторий скиллов для разработки 1С на macOS

Форк [Nikolay-Shirokov/cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills), ветка `mac-port`.
Python-only (PowerShell удалён), macOS-first.

## Использование в проектах

Проекты подключают скиллы через симлинк:
```bash
ln -s ~/Documents/github_dev/1C2Claude/.claude/skills <project>/.claude/skills
```
Активные: kabitoriy, chronicon.

## Структура

```
.claude/skills/
  _lib/
    v8_platform.py     # общий модуль: resolve_v8path(), find_project_root()
  env-setup/           # проверка/установка окружения, создание .v8-project.json
  bsl-check/           # анализ кода через BSL Language Server
  cf-build/            # сборка .cf/.cfe из XML-исходников
  test-yaxunit/        # прогон YAxUnit тестов
  bsp-merge/           # слияние с БСП через MergeCfg
  bsp-attach-files/    # создание справочника присоединённых файлов
  bsp-fill-types/      # заполнение определяемых типов из JSON
  cf-sort-children/    # сортировка ChildObjects в Configuration.xml
  ... (80+ скиллов)
```

## Правила добавления скиллов

- Платформо-зависимый код — только через `_lib/v8_platform.py` (не хардкодить пути)
- Имена объектов 1С — параметры CLI, не хардкод
- Перед коммитом: `python3 -m py_compile script.py` или `bash -n script.sh`
- Коммит в ветку `mac-port`, пуш в `https://github.com/iMironRU/cc-1c-skills`

## Если в проекте появился полезный скрипт

1. Обобщить (убрать хардкод, добавить параметры)
2. Добавить в `.claude/skills/<name>/` с `SKILL.md` и `scripts/`
3. Закоммитить — все проекты получат через симлинк

## Окружение

- Платформа 1С: `/opt/1cv8/8.3.27.2130/`
- BSL Language Server: VS Code расширение `1c-syntax.language-1c-bsl` v0.29.0
- Java: `/Library/Java/JavaVirtualMachines/axiomjdk-jdk-pro-17-full.jdk`
