#!/usr/bin/env python3
"""Sort <ChildObjects> in Configuration.xml to canonical 1C platform order."""

import re
import sys
from pathlib import Path

CANONICAL = [
    'Language', 'Subsystem', 'StyleItem', 'Style',
    'CommonPicture', 'SessionParameter', 'Role', 'CommonTemplate',
    'FilterCriterion', 'CommonModule', 'CommonAttribute', 'ExchangePlan',
    'XDTOPackage', 'WebService', 'HTTPService', 'WSReference',
    'EventSubscription', 'ScheduledJob', 'SettingsStorage', 'FunctionalOption',
    'FunctionalOptionsParameter', 'DefinedType', 'CommonCommand', 'CommandGroup',
    'Constant', 'CommonForm', 'Catalog', 'Document',
    'DocumentNumerator', 'Sequence', 'DocumentJournal', 'Enum',
    'Report', 'DataProcessor', 'InformationRegister', 'AccumulationRegister',
    'ChartOfCharacteristicTypes', 'ChartOfAccounts', 'AccountingRegister',
    'ChartOfCalculationTypes', 'CalculationRegister',
    'BusinessProcess', 'Task', 'IntegrationService',
]
ORDER = {t: i for i, t in enumerate(CANONICAL)}


def find_configuration_xml():
    """Search for Configuration.xml in standard locations."""
    candidates = [
        Path('Configuration.xml'),
        Path('src/Configuration.xml'),
        Path('src/cf/Configuration.xml'),
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def main():
    if len(sys.argv) > 1:
        cfg = Path(sys.argv[1])
    else:
        cfg = find_configuration_xml()
        if cfg is None:
            print('Error: Configuration.xml не найден. Укажите путь как аргумент.', file=sys.stderr)
            sys.exit(1)

    if not cfg.is_file():
        print(f'Error: файл не найден: {cfg}', file=sys.stderr)
        sys.exit(1)

    text = cfg.read_text(encoding='utf-8')
    m = re.search(r'(<ChildObjects>)(.*?)(</ChildObjects>)', text, re.DOTALL)
    if not m:
        print('Error: <ChildObjects> не найден в файле', file=sys.stderr)
        sys.exit(1)

    items = re.findall(r'<(\w+)>([^<]+)</\1>', m.group(2))
    items.sort(key=lambda kv: (ORDER.get(kv[0], 999), kv[1]))

    new_inner = '\n' + '\n'.join(f'\t\t\t<{tag}>{name}</{tag}>' for tag, name in items) + '\n\t\t'
    new_text = text[:m.start(2)] + new_inner + text[m.end(2):]

    if new_text == text:
        print(f'Already sorted: {len(items)} elements in {cfg}')
    else:
        cfg.write_text(new_text, encoding='utf-8')
        print(f'Sorted {len(items)} ChildObjects in {cfg}')


if __name__ == '__main__':
    main()
