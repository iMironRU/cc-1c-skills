---
name: cf-sort-children
description: Сортировка ChildObjects в Configuration.xml по каноническому порядку 1С. Используй после batch meta-compile или ручного добавления объектов метаданных
argument-hint: [path/to/Configuration.xml]
allowed-tools:
  - Bash
  - Read
---

# /cf-sort-children — Сортировка ChildObjects

Сортирует элементы `<ChildObjects>` в `Configuration.xml` по каноническому порядку платформы 1С.

## Зачем

`cf-validate` выдаёт warning "Type X is out of canonical order" если элементы не в правильном порядке. Запускайте после batch `meta-compile` или ручного добавления объектов.

## Usage

```
/cf-sort-children                        — ищет Configuration.xml в src/
/cf-sort-children path/to/Configuration.xml
```

## Команда

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/cf-sort-children.py" [path/to/Configuration.xml]
```

Если путь не указан — ищет `Configuration.xml` в стандартных местах: `src/Configuration.xml`, `src/cf/Configuration.xml`.

## Канонический порядок

Language → Subsystem → StyleItem → Style → CommonPicture → SessionParameter → Role → CommonTemplate → FilterCriterion → CommonModule → CommonAttribute → ExchangePlan → XDTOPackage → WebService → HTTPService → WSReference → EventSubscription → ScheduledJob → SettingsStorage → FunctionalOption → FunctionalOptionsParameter → DefinedType → CommonCommand → CommandGroup → Constant → CommonForm → Catalog → Document → DocumentNumerator → Sequence → DocumentJournal → Enum → Report → DataProcessor → InformationRegister → AccumulationRegister → ChartOfCharacteristicTypes → ChartOfAccounts → AccountingRegister → ChartOfCalculationTypes → CalculationRegister → BusinessProcess → Task → IntegrationService
