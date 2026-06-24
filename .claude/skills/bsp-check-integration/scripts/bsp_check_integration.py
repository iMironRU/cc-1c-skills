#!/usr/bin/env python3
"""BSP integration checker — static analysis of 1C configuration XML sources.

Checks that BSP (Библиотека Стандартных Подсистем) subsystems are correctly
integrated without running the 1C platform. Works directly on XML source files.

Based on «ПроверкаВнедренияБСП» report logic.
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '_lib'))
from v8_platform import find_project_root

NS = {'m': 'http://v8.1c.ru/8.3/MDClasses'}

SEV_ICON = {'error': '✗', 'warning': '△', 'info': 'ℹ'}
SEV_ORDER = {'error': 0, 'warning': 1, 'info': 2}

OBJ_DIRS = {
    'Catalog': 'Catalogs',
    'Document': 'Documents',
    'CommonModule': 'CommonModules',
    'InformationRegister': 'InformationRegisters',
    'AccumulationRegister': 'AccumulationRegisters',
    'BusinessProcess': 'BusinessProcesses',
    'Task': 'Tasks',
    'ChartOfCharacteristicTypes': 'ChartsOfCharacteristicTypes',
    'ExchangePlan': 'ExchangePlans',
    'Report': 'Reports',
    'DataProcessor': 'DataProcessors',
    'Enum': 'Enums',
}


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    subsystem: str
    severity: str       # error / warning / info
    obj: str            # e.g. "Catalog.МойСправочник"
    message: str
    detail: str = ''


# ---------------------------------------------------------------------------
# Config reader (lazy XML parsing)
# ---------------------------------------------------------------------------

class Config:
    def __init__(self, src_dir: Path):
        self.src = src_dir
        self._cfg_tree: Optional[ET.Element] = None
        self._dt_cache: dict = {}
        self._attr_cache: dict = {}
        self._ts_cache: dict = {}
        self._subsystems: Optional[set] = None

    # -- Config.xml ----------------------------------------------------------

    def _cfg(self) -> ET.Element:
        if self._cfg_tree is None:
            path = self.src / 'Configuration.xml'
            if not path.exists():
                raise FileNotFoundError(f'Configuration.xml не найден: {path}')
            self._cfg_tree = ET.parse(path).getroot()
        return self._cfg_tree

    def subsystems(self) -> set:
        """Names of all subsystems in the configuration."""
        if self._subsystems is None:
            self._subsystems = set()
            sub_dir = self.src / 'Subsystems'
            if sub_dir.is_dir():
                for f in sub_dir.glob('*.xml'):
                    self._subsystems.add(f.stem)
        return self._subsystems

    def objects_of_type(self, obj_type: str) -> list:
        """List of names for a given metadata type ('Catalog', 'Document', …)."""
        d = self.src / OBJ_DIRS.get(obj_type, obj_type + 's')
        if not d.is_dir():
            return []
        return [f.stem for f in d.glob('*.xml') if not f.stem.startswith('_')]

    # -- Object XML ----------------------------------------------------------

    def _obj_xml(self, obj_type: str, name: str) -> Optional[ET.Element]:
        d = OBJ_DIRS.get(obj_type, obj_type + 's')
        p = self.src / d / f'{name}.xml'
        if not p.exists():
            return None
        return ET.parse(p).getroot()

    def _obj_props(self, obj_type: str, name: str) -> Optional[ET.Element]:
        root = self._obj_xml(obj_type, name)
        if root is None:
            return None
        # Try namespaced and non-namespaced
        for tag in [f'{obj_type}', f'{{http://v8.1c.ru/8.3/MDClasses}}{obj_type}']:
            el = root.find(f'.//{tag}/Properties') or root.find(f'.//{tag}')
            if el is not None:
                props = el.find('Properties') if el.tag.endswith(obj_type) else el
                return props
        # Fallback: first child's Properties
        for child in root:
            props = child.find('Properties')
            if props is not None:
                return props
        return None

    def attributes(self, obj_type: str, name: str) -> list:
        """Return list of attribute names for an object."""
        key = (obj_type, name, 'attrs')
        if key not in self._attr_cache:
            result = []
            props = self._obj_props(obj_type, name)
            if props is not None:
                for attr in props.iter('Attribute'):
                    n = attr.find('Properties/Name') or attr.find('Name')
                    if n is not None and n.text:
                        result.append(n.text)
            self._attr_cache[key] = result
        return self._attr_cache[key]

    def attribute_types(self, obj_type: str, name: str, attr_name: str) -> list:
        """Return list of type strings for a specific attribute."""
        props = self._obj_props(obj_type, name)
        if props is None:
            return []
        for attr in props.iter('Attribute'):
            n = attr.find('Properties/Name') or attr.find('Name')
            if n is not None and n.text == attr_name:
                return [t.text for t in attr.iter('Type') if t.text and '.' in t.text]
        return []

    def tabular_sections(self, obj_type: str, name: str) -> list:
        """Return list of tabular section names."""
        key = (obj_type, name, 'ts')
        if key not in self._ts_cache:
            result = []
            props = self._obj_props(obj_type, name)
            if props is not None:
                for ts in props.iter('TabularSection'):
                    n = ts.find('Properties/Name') or ts.find('Name')
                    if n is not None and n.text:
                        result.append(n.text)
            self._ts_cache[key] = result
        return self._ts_cache[key]

    def ts_attributes(self, obj_type: str, name: str, ts_name: str) -> list:
        """Return attribute names of a tabular section."""
        props = self._obj_props(obj_type, name)
        if props is None:
            return []
        for ts in props.iter('TabularSection'):
            n = ts.find('Properties/Name') or ts.find('Name')
            if n is None or n.text != ts_name:
                continue
            result = []
            for attr in ts.iter('Attribute'):
                an = attr.find('Properties/Name') or attr.find('Name')
                if an is not None and an.text:
                    result.append(an.text)
            return result
        return []

    def ts_attr_types(self, obj_type: str, name: str, ts_name: str, attr_name: str) -> list:
        """Return type strings for a tabular section attribute."""
        props = self._obj_props(obj_type, name)
        if props is None:
            return []
        for ts in props.iter('TabularSection'):
            n = ts.find('Properties/Name') or ts.find('Name')
            if n is None or n.text != ts_name:
                continue
            for attr in ts.iter('Attribute'):
                an = attr.find('Properties/Name') or attr.find('Name')
                if an is not None and an.text == attr_name:
                    return [t.text for t in attr.iter('Type') if t.text and '.' in t.text]
        return []

    # -- Defined types -------------------------------------------------------

    def defined_type_members(self, dt_name: str) -> list:
        """Return list of type strings in a defined type (e.g. 'CatalogRef.X')."""
        if dt_name not in self._dt_cache:
            p = self.src / 'DefinedTypes' / f'{dt_name}.xml'
            if not p.exists():
                self._dt_cache[dt_name] = []
            else:
                root = ET.parse(p).getroot()
                self._dt_cache[dt_name] = [
                    t.text for t in root.iter('Type') if t.text and '.' in t.text
                ]
        return self._dt_cache[dt_name]

    def in_defined_type(self, dt_name: str, obj_type: str, obj_name: str) -> bool:
        prefix = f'{obj_type}Ref.{obj_name}'
        return any(m == prefix or m.endswith(f'.{obj_name}') for m in self.defined_type_members(dt_name))

    # -- BSL modules ---------------------------------------------------------

    def _bsl(self, path: Path) -> str:
        if path.exists():
            try:
                return path.read_text(encoding='utf-8-sig')
            except Exception:
                return ''
        return ''

    def manager_module(self, obj_type: str, name: str) -> str:
        d = OBJ_DIRS.get(obj_type, obj_type + 's')
        return self._bsl(self.src / d / name / 'Ext' / 'ManagerModule.bsl')

    def object_module(self, obj_type: str, name: str) -> str:
        d = OBJ_DIRS.get(obj_type, obj_type + 's')
        return self._bsl(self.src / d / name / 'Ext' / 'ObjectModule.bsl')

    def common_module(self, name: str) -> str:
        return self._bsl(self.src / 'CommonModules' / name / 'Ext' / 'Module.bsl')

    def all_common_modules(self):
        """Yield (name, bsl_text) for all common modules."""
        d = self.src / 'CommonModules'
        if not d.is_dir():
            return
        for mod_dir in d.iterdir():
            if mod_dir.is_dir():
                bsl = self._bsl(mod_dir / 'Ext' / 'Module.bsl')
                if bsl:
                    yield mod_dir.name, bsl

    def form_modules(self, obj_type: str, name: str) -> dict:
        """Return dict {form_name: bsl_text} for all forms of an object."""
        d = OBJ_DIRS.get(obj_type, obj_type + 's')
        forms_dir = self.src / d / name / 'Forms'
        result = {}
        if forms_dir.is_dir():
            for form_dir in forms_dir.iterdir():
                if form_dir.is_dir():
                    bsl = self._bsl(form_dir / 'Ext' / 'Form' / 'Module.bsl')
                    if bsl:
                        result[form_dir.name] = bsl
        return result

    def object_form_module(self, obj_type: str, name: str) -> tuple:
        """Return (form_name, bsl_text) for the object form (ФормаОбъекта / ФормаЭлемента)."""
        for form_forms in self.form_modules(obj_type, name).items():
            fn = form_forms[0].lower()
            if 'объект' in fn or 'элемент' in fn or 'formelement' in fn or 'formobject' in fn:
                return form_forms
        # Fallback: first form
        forms = self.form_modules(obj_type, name)
        if forms:
            return next(iter(forms.items()))
        return ('', '')


# ---------------------------------------------------------------------------
# Base checker
# ---------------------------------------------------------------------------

class BaseChecker:
    name = ''
    title = ''

    def check(self, cfg: Config) -> list:
        return []

    def _has_call(self, bsl: str, *patterns: str) -> bool:
        """True if ANY of the patterns appears in the BSL text."""
        for p in patterns:
            if re.search(p, bsl, re.IGNORECASE):
                return True
        return False

    def _has_proc(self, bsl: str, proc_name: str) -> bool:
        """True if a Procedure/Function with this name is defined in the BSL text."""
        return bool(re.search(
            rf'(Процедура|Функция|Procedure|Function)\s+{re.escape(proc_name)}\s*\(',
            bsl, re.IGNORECASE
        ))

    def _call_in_proc(self, bsl: str, proc_name: str, call_pattern: str) -> bool:
        """True if call_pattern is found inside the named procedure/function."""
        # Extract procedure body
        m = re.search(
            rf'(?:Процедура|Функция|Procedure|Function)\s+{re.escape(proc_name)}\s*\([^)]*\)[^\n]*\n'
            rf'(.*?)'
            rf'(?:КонецПроцедуры|КонецФункции|EndProcedure|EndFunction)',
            bsl, re.DOTALL | re.IGNORECASE
        )
        if not m:
            return False
        return bool(re.search(call_pattern, m.group(1), re.IGNORECASE))

    def err(self, subsystem, obj, msg, detail=''):
        return CheckResult(subsystem, 'error', obj, msg, detail)

    def warn(self, subsystem, obj, msg, detail=''):
        return CheckResult(subsystem, 'warning', obj, msg, detail)

    def info(self, subsystem, obj, msg, detail=''):
        return CheckResult(subsystem, 'info', obj, msg, detail)


# ---------------------------------------------------------------------------
# Checkers
# ---------------------------------------------------------------------------

class WorkWithFilesChecker(BaseChecker):
    """РаботаСФайлами — file attachment subsystem."""
    name = 'РаботаСФайлами'
    title = 'Работа с файлами'

    OWNER_DT = 'ВладелецПрисоединенныхФайлов'
    OWNER_OBJ_DT = 'ВладелецПрисоединенныхФайловОбъект'
    FILE_DT = 'ПрисоединенныйФайл'
    FILE_OBJ_DT = 'ПрисоединенныйФайлОбъект'

    REQUIRED_ATTRS = {
        'Автор', 'ВладелецФайла', 'ДатаМодификацииУниверсальная', 'ДатаСоздания',
        'Зашифрован', 'Изменил', 'Описание', 'ПодписанЭП', 'ПутьКФайлу',
        'Размер', 'Расширение', 'Редактирует', 'ФайлХранилище', 'ХранитьВерсии',
    }

    def check(self, cfg: Config) -> list:
        results = []
        file_catalogs = []
        owner_refs = set(cfg.defined_type_members(self.OWNER_DT))

        for cat in cfg.objects_of_type('Catalog'):
            if cat.endswith('ПрисоединенныеФайлы'):
                file_catalogs.append(cat)

        for cat in file_catalogs:
            obj = f'Catalog.{cat}'
            attrs = set(cfg.attributes('Catalog', cat))

            # Required attributes
            missing = self.REQUIRED_ATTRS - attrs
            if missing:
                results.append(self.warn(self.name, obj,
                    f'Нет обязательных реквизитов: {", ".join(sorted(missing))}'))

            # Must be in ПрисоединенныйФайл defined type
            if not cfg.in_defined_type(self.FILE_DT, 'Catalog', cat):
                results.append(self.err(self.name, obj,
                    f'Не включён в ОпределяемыйТип.{self.FILE_DT}'))
            if not cfg.in_defined_type(self.FILE_OBJ_DT, 'Catalog', cat):
                results.append(self.warn(self.name, obj,
                    f'Не включён в ОпределяемыйТип.{self.FILE_OBJ_DT}'))

            # ВладелецФайла attribute — its types must be in ВладелецПрисоединенныхФайлов
            if 'ВладелецФайла' in attrs:
                owner_types = cfg.attribute_types('Catalog', cat, 'ВладелецФайла')
                for ot in owner_types:
                    if ot not in owner_refs:
                        results.append(self.warn(self.name, obj,
                            f'Тип владельца {ot} отсутствует в ОпределяемыйТип.{self.OWNER_DT}'))

        # Check owner objects — form modules must have required calls
        FORM_CALLS = [
            ('РаботаСФайлами.ПриСозданииНаСервере', 'ПриСозданииНаСервере',
             r'РаботаСФайлами\.ПриСозданииНаСервере'),
            ('РаботаСФайламиКлиент.ПриОткрытии', 'ПриОткрытии',
             r'РаботаСФайламиКлиент\.ПриОткрытии'),
            ('РаботаСФайламиКлиент.ОбработкаОповещения', 'ОбработкаОповещения',
             r'РаботаСФайламиКлиент\.ОбработкаОповещения'),
        ]
        for ref in owner_refs:
            if not ref.startswith('CatalogRef.') and not ref.startswith('DocumentRef.'):
                continue
            parts = ref.split('.')
            if len(parts) != 2:
                continue
            otype_map = {'CatalogRef': 'Catalog', 'DocumentRef': 'Document'}
            otype = otype_map.get(parts[0])
            oname = parts[1]
            if not otype:
                continue
            _, form_bsl = cfg.object_form_module(otype, oname)
            if not form_bsl:
                continue
            obj = f'{otype}.{oname}'
            for call_name, proc_name, pattern in FORM_CALLS:
                if not self._call_in_proc(form_bsl, proc_name, pattern):
                    results.append(self.warn(self.name, obj,
                        f'В форме нет вызова {call_name}() в процедуре {proc_name}()'))

        return results


class ContactInfoChecker(BaseChecker):
    """КонтактнаяИнформация — contact information subsystem."""
    name = 'КонтактнаяИнформация'
    title = 'Контактная информация'

    OWNER_DT = 'ВладелецКонтактнойИнформации'
    TS_NAME = 'КонтактнаяИнформация'
    REQUIRED_TS_ATTRS = {
        'Тип': 'EnumRef.ТипыКонтактнойИнформации',
        'Вид': 'CatalogRef.ВидыКонтактнойИнформации',
        'Представление': None,  # Строка, тип не проверяем точно
    }

    def check(self, cfg: Config) -> list:
        results = []
        owner_refs = set(cfg.defined_type_members(self.OWNER_DT))

        for obj_type in ('Catalog', 'Document'):
            for name in cfg.objects_of_type(obj_type):
                obj = f'{obj_type}.{name}'
                ts_list = cfg.tabular_sections(obj_type, name)
                if self.TS_NAME not in ts_list:
                    continue

                # Has КонтактнаяИнформация TS — check it's registered in defined type
                ref = f'{obj_type}Ref.{name}'
                if ref not in owner_refs:
                    results.append(self.err(self.name, obj,
                        f'Есть ТЧ КонтактнаяИнформация, но объект не в ОпределяемыйТип.{self.OWNER_DT}'))

                # Check required TS attributes
                ts_attrs = cfg.ts_attributes(obj_type, name, self.TS_NAME)
                for required in self.REQUIRED_TS_ATTRS:
                    if required not in ts_attrs:
                        results.append(self.err(self.name, obj,
                            f'В ТЧ КонтактнаяИнформация нет реквизита «{required}»'))

                # Check Тип attribute type
                if 'Тип' in ts_attrs:
                    types = cfg.ts_attr_types(obj_type, name, self.TS_NAME, 'Тип')
                    if not any('ТипыКонтактнойИнформации' in t for t in types):
                        results.append(self.err(self.name, obj,
                            'Реквизит ТЧ КонтактнаяИнформация.Тип должен иметь тип '
                            'ПеречислениеСсылка.ТипыКонтактнойИнформации'))

                if 'Вид' in ts_attrs:
                    types = cfg.ts_attr_types(obj_type, name, self.TS_NAME, 'Вид')
                    if not any('ВидыКонтактнойИнформации' in t for t in types):
                        results.append(self.err(self.name, obj,
                            'Реквизит ТЧ КонтактнаяИнформация.Вид должен иметь тип '
                            'СправочникСсылка.ВидыКонтактнойИнформации'))

        return results


class ElectronicSignatureChecker(BaseChecker):
    """ЭлектроннаяПодпись — electronic signature subsystem."""
    name = 'ЭлектроннаяПодпись'
    title = 'Электронная подпись'

    SIGNED_DT = 'ПодписанныйОбъект'
    ATTR_NAME = 'ПодписанЭП'

    def check(self, cfg: Config) -> list:
        results = []
        signed_refs = set(cfg.defined_type_members(self.SIGNED_DT))

        for obj_type in ('Catalog', 'Document', 'ChartOfCharacteristicTypes',
                         'BusinessProcess', 'Task'):
            for name in cfg.objects_of_type(obj_type):
                obj = f'{obj_type}.{name}'
                attrs = cfg.attributes(obj_type, name)
                if self.ATTR_NAME not in attrs:
                    continue
                ref = f'{obj_type}Ref.{name}'
                if ref not in signed_refs:
                    results.append(self.err(self.name, obj,
                        f'Есть реквизит {self.ATTR_NAME}, но объект не в '
                        f'ОпределяемыйТип.{self.SIGNED_DT}'))

        return results


class PropertiesChecker(BaseChecker):
    """Свойства — additional attributes and properties subsystem."""
    name = 'Свойства'
    title = 'Дополнительные реквизиты и свойства'

    TS_NAME = 'ДополнительныеРеквизиты'
    REQUIRED_TS_ATTRS = {'Свойство', 'ТекстоваяСтрока', 'Значение'}
    PROP_TYPE_REF = 'ПланВидовХарактеристикСсылка.ДополнительныеРеквизитыИСведения'

    FORM_CALLS = [
        ('УправлениеСвойствами.ПриСозданииНаСервере', 'ПриСозданииНаСервере',
         r'УправлениеСвойствами\.ПриСозданииНаСервере'),
        ('УправлениеСвойствами.ПриЧтенииНаСервере', 'ПриЧтенииНаСервере',
         r'УправлениеСвойствами\.ПриЧтенииНаСервере'),
        ('УправлениеСвойствами.ПередЗаписьюНаСервере', 'ПередЗаписьюНаСервере',
         r'УправлениеСвойствами\.ПередЗаписьюНаСервере'),
    ]

    def check(self, cfg: Config) -> list:
        results = []

        for obj_type in ('Catalog', 'Document', 'BusinessProcess', 'Task',
                         'ChartOfCharacteristicTypes'):
            for name in cfg.objects_of_type(obj_type):
                obj = f'{obj_type}.{name}'
                ts_list = cfg.tabular_sections(obj_type, name)
                if self.TS_NAME not in ts_list:
                    continue

                # Check ТЧ structure
                ts_attrs = cfg.ts_attributes(obj_type, name, self.TS_NAME)
                for req in self.REQUIRED_TS_ATTRS:
                    if req not in ts_attrs:
                        results.append(self.warn(self.name, obj,
                            f'В ТЧ ДополнительныеРеквизиты нет реквизита «{req}»'))

                # Check Свойство type
                if 'Свойство' in ts_attrs:
                    types = cfg.ts_attr_types(obj_type, name, self.TS_NAME, 'Свойство')
                    if not any('ДополнительныеРеквизитыИСведения' in t for t in types):
                        results.append(self.err(self.name, obj,
                            'ТЧ ДополнительныеРеквизиты.Свойство должен иметь тип '
                            f'{self.PROP_TYPE_REF}'))

                # Check form module calls
                _, form_bsl = cfg.object_form_module(obj_type, name)
                if form_bsl:
                    for call_name, proc_name, pattern in self.FORM_CALLS:
                        if not self._call_in_proc(form_bsl, proc_name, pattern):
                            results.append(self.warn(self.name, obj,
                                f'В форме нет вызова {call_name}() в {proc_name}()'))

        return results


class AttachableCommandsChecker(BaseChecker):
    """ПодключаемыеКоманды — attachable commands subsystem."""
    name = 'ПодключаемыеКоманды'
    title = 'Подключаемые команды'

    SUBSYSTEM_MODULES = {
        'print': 'УправлениеПечатьюПереопределяемый',
        'reports': 'ВариантыОтчетовПереопределяемый',
        'fill': 'ЗаполнениеОбъектовПереопределяемый',
    }
    PROC_PATTERNS = {
        'print': r'ДобавитьКомандыПечати',
        'reports': r'ДобавитьКомандыОтчетов',
        'fill': r'ДобавитьКомандыЗаполнения',
    }
    FORM_REQUIRED = [
        ('ПриСозданииНаСервере', r'ПодключаемыеКоманды\.ПриСозданииНаСервере'),
        ('ПослеЗаписи', r'ПодключаемыеКомандыКлиент\.ПослеЗаписи'),
    ]
    FORM_PROCS = [
        'Подключаемый_ВыполнитьКоманду',
        'Подключаемый_ОбновитьКоманды',
    ]

    def _registered_objects(self, cfg: Config, mod_key: str) -> set:
        """Parse переопределяемый module to find registered objects."""
        mod_name = self.SUBSYSTEM_MODULES[mod_key]
        bsl = cfg.common_module(mod_name)
        if not bsl:
            return set()
        # Find Добавить* procedure and extract object names from ТипОбъекта/Тип lines
        pattern = self.PROC_PATTERNS[mod_key]
        found = set()
        # Look for .Add("ObjectName") or Тип = "ObjectType.Name" patterns
        for m in re.finditer(r'["\']((?:Catalog|Document|Справочник|Документ)\.\w+)["\']', bsl):
            found.add(m.group(1))
        return found

    def check(self, cfg: Config) -> list:
        results = []

        for obj_type in ('Catalog', 'Document'):
            for name in cfg.objects_of_type(obj_type):
                obj = f'{obj_type}.{name}'
                mgr = cfg.manager_module(obj_type, name)
                if not mgr:
                    continue

                is_source = False
                for key, proc_re in self.PROC_PATTERNS.items():
                    if self._has_proc(mgr, proc_re.replace(r'\\', '').split(r'\b')[0]):
                        is_source = True
                        break

                if not is_source:
                    continue

                # Has attachable command procedures — check form
                _, form_bsl = cfg.object_form_module(obj_type, name)
                if not form_bsl:
                    results.append(self.warn(self.name, obj,
                        'Объект является источником команд, но нет формы объекта'))
                    continue

                for proc_name, pattern in self.FORM_REQUIRED:
                    if not self._call_in_proc(form_bsl, proc_name, pattern):
                        results.append(self.warn(self.name, obj,
                            f'В форме нет вызова ПодключаемыеКоманды в {proc_name}()'))

                for proc_name in self.FORM_PROCS:
                    if not self._has_proc(form_bsl, proc_name):
                        results.append(self.warn(self.name, obj,
                            f'В форме нет процедуры {proc_name}()'))

        return results


class VersioningChecker(BaseChecker):
    """ВерсионированиеОбъектов — object versioning subsystem."""
    name = 'ВерсионированиеОбъектов'
    title = 'Версионирование объектов'

    VERSIONED_DT = 'ВерсионируемыйОбъект'

    def check(self, cfg: Config) -> list:
        results = []
        if not (cfg.src / 'DefinedTypes' / f'{self.VERSIONED_DT}.xml').exists():
            return []

        versioned_refs = set(cfg.defined_type_members(self.VERSIONED_DT))

        # Check that objects registered in переопределяемый module are in defined type
        bsl = cfg.common_module('ВерсионированиеОбъектовПереопределяемый')
        if not bsl:
            return []

        for m in re.finditer(
            r'["\']((?:CatalogRef|DocumentRef|Справочник|Документ)\.\w+)["\']', bsl
        ):
            ref = m.group(1)
            if ref not in versioned_refs:
                results.append(self.warn(self.name, ref,
                    f'Объект в модуле ВерсионированиеОбъектовПереопределяемый, '
                    f'но не в ОпределяемыйТип.{self.VERSIONED_DT}'))

        return results


class UpdateVersionChecker(BaseChecker):
    """ОбновлениеВерсииИБ — database version update subsystem."""
    name = 'ОбновлениеВерсииИБ'
    title = 'Обновление версии ИБ'

    REQUIRED_CALLS = [
        r'ОбновлениеИнформационнойБазы\.ДобавитьПроцедуруОбновления',
        r'ОбновлениеИнформационнойБазыБСП\.ДобавитьПроцедуруОбновления',
    ]

    def check(self, cfg: Config) -> list:
        results = []
        # Check that переопределяемый module registers update handlers
        bsl = cfg.common_module('ОбновлениеИнформационнойБазыПереопределяемый')
        if not bsl:
            return []

        has_handler = any(self._has_call(bsl, p) for p in self.REQUIRED_CALLS)
        if not has_handler:
            # Конфигурации часто регистрируют обработчики в отдельном модуле
            for mod_name, mod_bsl in cfg.all_common_modules():
                if ('Обновление' in mod_name and 'Переопределяемый' not in mod_name
                        and any(self._has_call(mod_bsl, p) for p in self.REQUIRED_CALLS)):
                    has_handler = True
                    break
        if not has_handler:
            results.append(self.warn(self.name,
                'CommonModule.ОбновлениеИнформационнойБазыПереопределяемый',
                'Не найден вызов регистрации обработчиков обновления'))

        # Check all update handler procedures are valid
        for proc in re.finditer(
            r'Процедура\s+(\w+)\s*\(', bsl
        ):
            proc_name = proc.group(1)
            if 'Обновить' in proc_name or 'Update' in proc_name:
                # Should have ОбновлениеИнформационнойБазы calls
                body_match = re.search(
                    rf'Процедура\s+{re.escape(proc_name)}\s*\([^)]*\)[^\n]*\n(.*?)КонецПроцедуры',
                    bsl, re.DOTALL
                )
                if body_match and 'ОбновлениеИнформационнойБазы' not in body_match.group(1):
                    results.append(self.info(self.name,
                        f'CommonModule.ОбновлениеИнформационнойБазыПереопределяемый',
                        f'Процедура {proc_name} не использует ОбновлениеИнформационнойБазы'))

        return results


class ForbiddenDateChecker(BaseChecker):
    """ДатыЗапретаИзменения — forbidden change dates subsystem."""
    name = 'ДатыЗапретаИзменения'
    title = 'Даты запрета изменения'

    def check(self, cfg: Config) -> list:
        results = []
        bsl = cfg.common_module('ДатыЗапретаИзмененияПереопределяемый')
        if not bsl:
            return []

        if not self._has_proc(bsl, 'ЗаполнитьИсточникиДанныхДляПроверкиЗапретаИзменения'):
            results.append(self.warn(self.name,
                'CommonModule.ДатыЗапретаИзмененияПереопределяемый',
                'Нет процедуры ЗаполнитьИсточникиДанныхДляПроверкиЗапретаИзменения'))

        return results


class MultilanguageChecker(BaseChecker):
    """Мультиязычность — multilingual support subsystem."""
    name = 'Мультиязычность'
    title = 'Мультиязычность'

    FORM_CALLS = [
        ('ПриСозданииНаСервере', r'МультиязычностьСервер\.ПриСозданииНаСервере'),
        ('ПриЧтенииНаСервере', r'МультиязычностьСервер\.ПриЧтенииНаСервере'),
        ('ПередЗаписьюНаСервере', r'МультиязычностьСервер\.ПередЗаписьюНаСервере'),
    ]

    def check(self, cfg: Config) -> list:
        results = []
        bsl = cfg.common_module('МультиязычностьПереопределяемый')
        if not bsl:
            return []

        # Find objects registered for multilanguage
        for m in re.finditer(r'["\']((?:Catalog|Document)\.\w+)["\']', bsl):
            ref = m.group(1)
            parts = ref.split('.')
            if len(parts) != 2:
                continue
            otype = parts[0]
            oname = parts[1]
            obj = f'{otype}.{oname}'
            _, form_bsl = cfg.object_form_module(otype, oname)
            if not form_bsl:
                continue
            for proc_name, pattern in self.FORM_CALLS:
                if not self._call_in_proc(form_bsl, proc_name, pattern):
                    results.append(self.warn(self.name, obj,
                        f'В форме нет вызова МультиязычностьСервер в {proc_name}()'))

        return results


class OriginalDocumentsChecker(BaseChecker):
    """УчетОригиналовПервичныхДокументов — original primary documents subsystem."""
    name = 'УчетОригиналовПервичныхДокументов'
    title = 'Учет оригиналов первичных документов'

    REQUIRED_PROCS = [
        'Подключаемый_ДекорацияСостояниеОригиналаНажатие',
        'Подключаемый_ОбновитьКомандыСостоянияОригинала',
    ]

    def check(self, cfg: Config) -> list:
        results = []
        bsl = cfg.common_module('УчетОригиналовПервичныхДокументовПереопределяемый')
        if not bsl:
            return []

        for m in re.finditer(r'["\'](Document\.\w+)["\']', bsl):
            doc_name = m.group(1).split('.')[1]
            obj = f'Document.{doc_name}'
            _, form_bsl = cfg.object_form_module('Document', doc_name)
            if not form_bsl:
                continue
            for proc in self.REQUIRED_PROCS:
                if not self._has_proc(form_bsl, proc):
                    results.append(self.warn(self.name, obj,
                        f'В форме нет процедуры {proc}()'))
            if not self._call_in_proc(form_bsl, 'ПриСозданииНаСервере',
                                       r'УчетОригиналовПервичныхДокументов\.ПриСозданииНаСервере'):
                results.append(self.warn(self.name, obj,
                    'В форме нет вызова УчетОригиналовПервичныхДокументов.ПриСозданииНаСервере'))

        return results


class ReportOptionsChecker(BaseChecker):
    """ВариантыОтчетов — report options subsystem."""
    name = 'ВариантыОтчетов'
    title = 'Варианты отчетов'

    DT_REPORT = 'ОтчетОбъект'

    def check(self, cfg: Config) -> list:
        results = []
        bsl = cfg.common_module('ВариантыОтчетовПереопределяемый')
        if not bsl:
            return []

        for m in re.finditer(r'["\'](Report\.\w+)["\']', bsl):
            report_name = m.group(1).split('.')[1]
            mgr = cfg.manager_module('Report', report_name)
            if mgr and not self._has_proc(mgr, 'ДобавитьКомандыОтчетов'):
                results.append(self.warn(self.name, f'Report.{report_name}',
                    'Отчет в ВариантыОтчетовПереопределяемый, '
                    'но нет процедуры ДобавитьКомандыОтчетов() в модуле менеджера'))

        return results


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ALL_CHECKERS: list = [
    WorkWithFilesChecker(),
    ContactInfoChecker(),
    ElectronicSignatureChecker(),
    PropertiesChecker(),
    AttachableCommandsChecker(),
    VersioningChecker(),
    UpdateVersionChecker(),
    ForbiddenDateChecker(),
    MultilanguageChecker(),
    OriginalDocumentsChecker(),
    ReportOptionsChecker(),
]

CHECKER_MAP = {c.name: c for c in ALL_CHECKERS}


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_report(results: list, min_sev: str):
    threshold = SEV_ORDER.get(min_sev, 2)
    filtered = [r for r in results if SEV_ORDER.get(r.severity, 2) <= threshold]

    if not filtered:
        print('[ok] проблем не найдено')
        return True

    # Group by subsystem
    by_sub: dict = {}
    for r in filtered:
        by_sub.setdefault(r.subsystem, []).append(r)

    counts = {'error': 0, 'warning': 0, 'info': 0}
    for sub, items in sorted(by_sub.items()):
        print(f'\n── {sub} ──')
        for r in sorted(items, key=lambda x: (SEV_ORDER.get(x.severity, 2), x.obj)):
            icon = SEV_ICON.get(r.severity, '?')
            print(f'  {icon}  {r.obj}')
            print(f'       {r.message}')
            if r.detail:
                print(f'       {r.detail}')
            counts[r.severity] = counts.get(r.severity, 0) + 1

    print()
    parts = [f'{SEV_ICON[s]} {s.capitalize()}: {n}' for s, n in counts.items() if n]
    print('[итого] ' + '  '.join(parts))
    return counts.get('error', 0) == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def find_src_dir() -> Optional[Path]:
    root = find_project_root() or os.getcwd()
    for d in ('src/cf', 'src', '1c/standalone/src'):
        p = Path(root) / d
        if (p / 'Configuration.xml').exists():
            return p
    return None


def main():
    p = argparse.ArgumentParser(
        description='Проверка внедрения БСП по XML-исходникам конфигурации')
    p.add_argument('--src', default='',
                   help='Каталог исходников XML (авто-поиск если не указан)')
    p.add_argument('--subsystem', '-s', default='',
                   help='Проверить только указанную подсистему (напр. РаботаСФайлами)')
    p.add_argument('--list', action='store_true',
                   help='Показать список доступных проверок')
    p.add_argument('--severity', default='warning',
                   choices=['error', 'warning', 'info'],
                   help='Минимальный уровень вывода (умолч: warning)')
    args = p.parse_args()

    if args.list:
        print('Доступные проверки подсистем БСП:')
        for c in ALL_CHECKERS:
            print(f'  {c.name:40s} {c.title}')
        return

    src_dir = Path(args.src) if args.src else find_src_dir()
    if not src_dir:
        print('Error: каталог исходников не найден. Укажите --src', file=sys.stderr)
        sys.exit(1)
    if not (src_dir / 'Configuration.xml').exists():
        print(f'Error: Configuration.xml не найден в {src_dir}', file=sys.stderr)
        sys.exit(1)

    print(f'Источник: {src_dir}')

    checkers = ALL_CHECKERS
    if args.subsystem:
        if args.subsystem not in CHECKER_MAP:
            print(f'Error: подсистема «{args.subsystem}» не найдена. '
                  f'Доступны: {", ".join(CHECKER_MAP)}', file=sys.stderr)
            sys.exit(1)
        checkers = [CHECKER_MAP[args.subsystem]]

    cfg = Config(src_dir)
    results = []
    for checker in checkers:
        try:
            found = checker.check(cfg)
            if found:
                label = f'[{checker.name}] {len(found)} зам.'
            else:
                label = f'[{checker.name}] ok'
            print(label)
            results.extend(found)
        except Exception as e:
            print(f'[{checker.name}] ошибка проверки: {e}', file=sys.stderr)

    ok = print_report(results, args.severity)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
