---
name: test-yaxunit
description: Прогон YAxUnit-тестов 1С. Используй когда нужно запустить юнит-тесты, прогнать тесты YAxUnit
argument-hint: [--src <path>] [--tests <path>]
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /test-yaxunit — Прогон YAxUnit-тестов

Полный идемпотентный цикл: создание ИБ, загрузка конфигурации и расширений, снятие безопасного режима, прогон тестов, разбор jUnit-отчёта.

## Usage

```
/test-yaxunit                              — автоопределение из структуры проекта
/test-yaxunit --src src/cf --tests tests/src
```

## Команда

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/test-yaxunit.sh" [параметры]
```

### Параметры

| Параметр | Обязательный | Описание |
|----------|:------------:|----------|
| `--src <путь>` | нет | Каталог исходников конфигурации (default: auto-detect) |
| `--tests <путь>` | нет | Каталог исходников тестового расширения (default: auto-detect) |
| `--yaxunit <путь>` | нет | Путь к YAxUnit.cfe (default: `tools/yaxunit/YAxUnit.cfe`) |
| `--ext-name <имя>` | нет | Имя тестового расширения (default: `tests`) |
| `--timeout <сек>` | нет | Таймаут на каждый шаг (default: 240) |

## Требования

- YAxUnit.cfe — скачать с [github.com/bia-technologies/yaxunit](https://github.com/bia-technologies/yaxunit/releases)
- Опционально: `tools/yaxunit/DisableSafeMode.epf`

## Шаги

1. Свежая ИБ (изоляция тестовых данных)
2. Загрузка главной конфигурации
3. Загрузка расширения YAxUnit
4. Загрузка тестового расширения
5. Снятие безопасного режима
6. Прогон тестов (headless ENTERPRISE)
7. Разбор jUnit XML-отчёта
