---
name: bsp-fill-types
description: Заполнение БСП-определяемых типов ссылками на объекты конфигурации после MergeCfg. Используй после слияния с БСП для устранения ошибок «Недопустимый тип»
argument-hint: --types-map <json-file> [--unpack-dir <path>]
allowed-tools:
  - Bash
  - Read
  - Write
---

# /bsp-fill-types — Заполнение определяемых типов БСП

Заполняет пустые определяемые типы БСП ссылками на объекты конфигурации. Идемпотентен.

## Usage

```
/bsp-fill-types --types-map types-map.json
/bsp-fill-types --types-map types-map.json --unpack-dir base/bsp-merged-unpack
```

## Команда

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/bsp-fill-types.py" <параметры>
```

### Параметры

| Параметр | Обязательный | Описание |
|----------|:------------:|----------|
| `--types-map <путь>` | да | JSON-файл с маппингом: имя определяемого типа → список типов |
| `--unpack-dir <путь>` | нет | Каталог распакованной конфигурации (default: `base/bsp-merged-unpack`) |

## Формат types-map.json

```json
{
  "ВладелецПрисоединенныхФайлов": [
    "cfg:CatalogRef.МойСправочник"
  ],
  "ВерсионируемыеДанные": [
    "cfg:CatalogRef.МойСправочник",
    "cfg:DocumentRef.МойДокумент"
  ]
}
```

Если определяемый тип содержит placeholder (`xs:string`) — заменяет полностью. Если уже заполнен — добавляет недостающие типы. Повторный запуск не дублирует.
