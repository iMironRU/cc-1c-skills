# 1C Skills for Claude Code — Mac Edition

> Форк [cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills), адаптированный для **macOS**. Python-only, без PowerShell.

Набор навыков для [Claude Code](https://docs.anthropic.com/en/docs/claude-code/skills), охватывающий полный цикл разработки на платформе 1С:Предприятие 8.3 на Mac — от создания конфигураций, расширений, внешних обработок и отчётов до загрузки в информационную базу, публикации через Apache и тестирования через веб-клиент.

## Быстрый старт

```bash
# 1. Скопируйте .claude/skills/ в ваш проект
cp -r .claude/skills/ /path/to/your/project/.claude/skills/

# 2. Проверьте окружение
cd /path/to/your/project
claude
# затем: /env-setup --check
```

Или через симлинк (обновления подхватываются автоматически):

```bash
git clone https://github.com/iMironRU/cc-1c-skills.git ~/tools/cc-1c-skills
cd ~/tools/cc-1c-skills && git checkout mac-port
ln -s ~/tools/cc-1c-skills/.claude/skills /path/to/your/project/.claude/skills
```

## Что отличается от оригинала

| | Оригинал | Mac Edition |
|---|---|---|
| Рантайм | PowerShell (основной) + Python (порт) | Python-only |
| Платформа | Windows | macOS (+ Linux) |
| Пути 1С | `C:\Program Files\1cv8\` | `/opt/1cv8/` |
| Определение платформы | В каждом скрипте | Общий модуль `_lib/v8_platform.py` |
| BSL Language Server | — | Скилл `/env-setup` с автоустановкой |
| Сортировка ChildObjects | — | Скилл `/cf-sort-children` |

## Требования

- **macOS** с Python 3.10+
- **1С:Предприятие 8.3** для Linux/Mac (`/opt/1cv8/`)
- **Java 17+** — для BSL Language Server
- **lxml** и **psutil** — `pip3 install lxml psutil`
- **Node.js 18+** — для `/web-test` (тестирование через браузер)

Проверить всё разом: `/env-setup --check`

## Группы навыков

| Группа | Навыки | Описание |
|--------|--------|----------|
| Настройка окружения | `/env-setup` | Проверка и установка BSL LS, зависимостей, `.v8-project.json` |
| Внешние обработки (EPF) | 7 навыков `/epf-*` | Создание, сборка, разборка, валидация обработок |
| Внешние отчёты (ERF) | 4 навыка `/erf-*` | Создание, сборка, разборка, валидация отчётов |
| Универсальные операции | `/template-add`, `/template-remove`, `/help-add`, `/form-remove` | Макеты, формы, справка |
| Табличный документ (MXL) | 4 навыка `/mxl-*` | Анализ, создание, компиляция макетов |
| Управляемые формы (Form) | 6 навыков `/form-*` | Создание, анализ, генерация, валидация форм |
| Роли (Role) | 3 навыка `/role-*` | Анализ прав, создание из JSON DSL, валидация |
| Схема компоновки (СКД) | 4 навыка `/skd-*` | Анализ, генерация, редактирование, валидация СКД |
| Метаданные конфигурации | 5 навыков `/meta-*` | CRUD объектов метаданных (23 типа) |
| Корневая конфигурация | 5 навыков `/cf-*` | Создание, анализ, редактирование, валидация, сортировка |
| Расширения (CFE) | 5 навыков `/cfe-*` | Создание, заимствование, перехват методов, валидация |
| Подсистемы (Subsystem) | 4 навыка `/subsystem-*` | Анализ, создание, редактирование, валидация |
| Командный интерфейс | 2 навыка `/interface-*` | Редактирование и валидация CommandInterface.xml |
| Базы данных (DB) | 9 навыков `/db-*` | Создание баз, загрузка/выгрузка конфигураций, обновление |
| Веб-публикация (Web) | 4 навыка `/web-*` | Публикация через Apache, статус, остановка |
| Тестирование (Web) | `/web-test` | Взаимодействие с веб-клиентом 1С |
| Утилиты | `/img-grid` | Сетка для анализа изображений |

## Конфигурация проекта

Создайте `.v8-project.json` в корне проекта (или через `/env-setup --init-project`):

```json
{
  "v8path": "/opt/1cv8/8.3.27.2130",
  "databases": [
    {
      "id": "dev",
      "name": "Разработка",
      "path": "~/bases/dev",
      "configSrc": "src/cf",
      "default": true
    }
  ]
}
```

## Благодарности

Основано на [cc-1c-skills](https://github.com/Nikolay-Shirokov/cc-1c-skills) от [@Nikolay-Shirokov](https://github.com/Nikolay-Shirokov).
