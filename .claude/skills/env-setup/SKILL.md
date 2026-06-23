---
name: env-setup
description: Настройка окружения для разработки 1С на Mac. Устанавливает BSL Language Server, Python-зависимости, проверяет платформу 1С, создаёт .v8-project.json
argument-hint: [--check | --install | --bsl | --deps]
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /env-setup — Настройка окружения разработки 1С на Mac

Проверяет и устанавливает все компоненты для работы с навыками 1С на macOS.

## Usage

```
/env-setup              — полная проверка и установка
/env-setup --check      — только проверка (ничего не устанавливает)
/env-setup --bsl        — установить только BSL Language Server
/env-setup --deps       — установить только Python-зависимости
```

## Команда

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/env-setup.py" <параметры>
```

### Параметры скрипта

| Параметр | Описание |
|----------|----------|
| `--check` | Только диагностика — показать статус компонентов |
| `--install` | Установить все недостающие компоненты |
| `--bsl` | Установить только BSL Language Server |
| `--deps` | Установить только Python-зависимости (lxml, psutil) |
| `--init-project` | Создать .v8-project.json в текущем каталоге |

## Что проверяется и устанавливается

1. **Платформа 1С** — наличие в `/opt/1cv8/` или `/opt/1C/v8.3/`
2. **BSL Language Server** — синтаксический анализатор кода 1С (скачивается с GitHub)
3. **Java 17+** — требуется для BSL Language Server
4. **Python-зависимости** — `lxml` (DOM), `psutil` (управление процессами)
5. **Node.js 18+** — для `/web-test` (тестирование через браузер)
6. **Homebrew** — проверяет наличие для установки зависимостей

## После установки

BSL Language Server доступен как `bsl-language-server` для анализа кода 1С:
```bash
bsl-language-server --analyze --src ./src
```
