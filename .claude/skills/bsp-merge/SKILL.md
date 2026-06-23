---
name: bsp-merge
description: Слияние конфигурации с БСП через MergeCfg. Используй когда нужно внедрить БСП в конфигурацию, выполнить merge с библиотекой стандартных подсистем
argument-hint: [--bsp-cf <path>] [--settings <path>]
allowed-tools:
  - Bash
  - Read
  - Write
  - AskUserQuestion
---

# /bsp-merge — Слияние конфигурации с БСП

Полный цикл MergeCfg в 8 шагов: создание изолированной ИБ, загрузка исходников, слияние с БСП, post-merge патчинг определяемых типов, финальное обновление.

## Usage

```
/bsp-merge                                — интерактивно (спросит пути)
/bsp-merge --bsp-cf tools/bsp/bsp.cf      — указать CF БСП
```

## Команда

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/bsp-merge.sh" [параметры]
```

### Параметры

| Параметр | Обязательный | Описание |
|----------|:------------:|----------|
| `--bsp-cf <путь>` | да | Путь к CF-файлу БСП |
| `--settings <путь>` | нет | Путь к XML настроек внедрения (подсистемы для MergeCfg) |
| `--src <путь>` | нет | Каталог исходников конфигурации (default: `src/cf` или `1c/standalone/src`) |
| `--out <путь>` | нет | Каталог для merged-выгрузки (default: `base/bsp-merged-unpack`) |
| `--types-map <путь>` | нет | JSON-файл маппинга определяемых типов для post-merge |

## Шаги

1. Создаёт изолированную ИБ `base/merge-test-ib/`
2. LoadConfigFromFiles из исходников
3. UpdateDBCfg (каркас)
4. MergeCfg с БСП (-EnableSupport -force)
5. DumpConfigToFiles → merged-выгрузка
6. Post-merge: заполнение определяемых типов (если указан `--types-map`)
7. LoadConfigFromFiles patched
8. UpdateDBCfg (финал)

Исходники проекта НЕ трогаются. Merged-конфа остаётся в `base/bsp-merged-unpack/`.

## Пример types-map.json

```json
{
  "ВладелецПрисоединенныхФайлов": ["cfg:CatalogRef.МойСправочник"],
  "ВерсионируемыеДанные": ["cfg:CatalogRef.МойСправочник", "cfg:DocumentRef.МойДокумент"]
}
```
