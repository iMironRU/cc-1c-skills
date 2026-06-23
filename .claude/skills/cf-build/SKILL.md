---
name: cf-build
description: Сборка конфигурации 1С (.cf/.cfe) из XML-исходников. Используй когда нужно собрать CF или CFE файл из исходников
argument-hint: [--src <path>] [--out <path>]
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---

# /cf-build — Сборка конфигурации

Собирает .cf или .cfe файл из XML-исходников через временную ИБ.

## Usage

```
/cf-build                                  — автоопределение из .v8-project.json
/cf-build --src src/cf --out build/app.cf
/cf-build --src src/ext --out build/ext.cfe --extension МоёРасширение
```

## Команда

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/cf-build.sh" [параметры]
```

### Параметры

| Параметр | Обязательный | Описание |
|----------|:------------:|----------|
| `--src <путь>` | нет | Каталог исходников (default: `src/cf` или `1c/standalone/src`) |
| `--out <путь>` | нет | Путь к выходному файлу (default: `build/<project>.cf`) |
| `--extension <имя>` | нет | Имя расширения (если собираем .cfe) |
| `--timeout <сек>` | нет | Таймаут на каждый шаг (default: 300) |

## Шаги

1. Создаёт временную ИБ
2. LoadConfigFromFiles из исходников
3. UpdateDBCfg
4. DumpCfg → выходной файл
5. Удаляет временную ИБ
