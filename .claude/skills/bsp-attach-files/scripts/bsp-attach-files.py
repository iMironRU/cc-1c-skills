#!/usr/bin/env python3
"""Generate attached files catalog for BSP 'Work with Files' subsystem.

Generalized from chronicon/scripts/bsp-attach-owner.py — no hardcoded object names.
"""

import argparse
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '_lib'))
from v8_platform import find_project_root

DROP_ATTRIBUTES = {"СтатусИзвлеченияТекста", "ТипХраненияФайла", "Том"}
SIMPLIFY_AUTHOR_LIKE = {"Автор", "Изменил", "Редактирует"}


def find_src_dir():
    root = find_project_root() or os.getcwd()
    for d in ["src/cf", "src", "1c/standalone/src"]:
        p = os.path.join(root, d)
        if os.path.isfile(os.path.join(p, "Configuration.xml")):
            return Path(p)
    return None


def regen_uuids(text):
    text = re.sub(r'uuid="[0-9a-f-]{36}"',
                  lambda _: f'uuid="{uuid.uuid4()}"', text)
    text = re.sub(r'<xr:TypeId>[0-9a-f-]{36}</xr:TypeId>',
                  lambda _: f'<xr:TypeId>{uuid.uuid4()}</xr:TypeId>', text)
    text = re.sub(r'<xr:ValueId>[0-9a-f-]{36}</xr:ValueId>',
                  lambda _: f'<xr:ValueId>{uuid.uuid4()}</xr:ValueId>', text)
    return text


def rename(text, owner_name, new_name, synonym_owner):
    repl = [
        ("_ДемоПроектыПрисоединенныеФайлы", new_name),
        ("CatalogRef._ДемоПроекты", f"CatalogRef.{owner_name}"),
        ("Catalog._ДемоПроекты.", f"Catalog.{owner_name}."),
        ("Catalog._ДемоНоменклатура.EmptyRef", f"Catalog.{owner_name}.EmptyRef"),
        ("Catalog.ВнешниеПользователи.EmptyRef", "Catalog.Пользователи.EmptyRef"),
        ("Присоединенные файлы (Демо: Проекты)",
         f"Присоединённые файлы ({synonym_owner})"),
        ("Присоединенный файл (Демо: Проекты)",
         f"Присоединённый файл ({synonym_owner})"),
    ]
    for a, b in repl:
        text = text.replace(a, b)
    return text


def drop_attributes(text, names):
    for name in names:
        pattern = (
            r'\n\t\t\t<Attribute uuid="[^"]+">'
            r'(?:(?!<Attribute uuid).)*?'
            rf'<Name>{re.escape(name)}</Name>'
            r'(?:(?!</Attribute>).)*?'
            r'</Attribute>'
        )
        text, n = re.subn(pattern, "", text, flags=re.DOTALL)
        if n:
            print(f"[drop-attr] {name}")
    return text


def drop_tabular_sections(text):
    pattern = r'\n\t\t\t<TabularSection uuid="[^"]+">(?:(?!<TabularSection uuid).)*?</TabularSection>'
    text, n = re.subn(pattern, "", text, flags=re.DOTALL)
    print(f"[drop-ts] удалено TabularSection: {n}")
    return text


def simplify_composite_types(text, names):
    for name in names:
        attr_re = re.compile(
            rf'(<Attribute uuid="[^"]+">(?:(?!</Attribute>).)*?'
            rf'<Name>{re.escape(name)}</Name>(?:(?!</Attribute>).)*?'
            rf'<Type>)(.*?)(</Type>)',
            re.DOTALL,
        )
        def _strip(m):
            type_body = m.group(2)
            keep = re.findall(
                r'<v8:Type>cfg:CatalogRef\.Пользователи</v8:Type>', type_body)
            if not keep:
                return m.group(0)
            new_body = "\n\t\t\t\t\t\t" + keep[0] + "\n\t\t\t\t\t"
            return m.group(1) + new_body + m.group(3)
        text, n = attr_re.subn(_strip, text)
        print(f"[simplify-type] {name}: {n}")
    return text


def register_in_configuration(config_xml, new_name):
    text = config_xml.read_text(encoding="utf-8")
    entry = f"<Catalog>{new_name}</Catalog>"
    if entry in text:
        print(f"[skip-register] {new_name} уже в Configuration.xml")
        return
    text = text.replace(
        "</ChildObjects>",
        f"\t\t\t{entry}\n\t\t</ChildObjects>",
        1,
    )
    config_xml.write_text(text, encoding="utf-8")
    print(f"[register] {new_name} → Configuration.xml")


def main():
    p = argparse.ArgumentParser(description="Generate BSP attached files catalog")
    p.add_argument("--owner-name", required=True)
    p.add_argument("--new-name", required=True)
    p.add_argument("--synonym-owner", required=True)
    p.add_argument("--demo-xml", default="")
    p.add_argument("--src-dir", default="")
    p.add_argument("--register", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    src_dir = Path(args.src_dir) if args.src_dir else find_src_dir()
    if not src_dir:
        print("Error: каталог исходников не найден. Укажите --src-dir", file=sys.stderr)
        sys.exit(1)

    demo_xml = Path(args.demo_xml) if args.demo_xml else None
    if not demo_xml:
        root = find_project_root() or os.getcwd()
        demo_xml = Path(root) / "base/bsp-demo-unpack/Catalogs/_ДемоПроектыПрисоединенныеФайлы.xml"

    out_dir = src_dir / "Catalogs"
    out_path = out_dir / f"{args.new_name}.xml"

    if out_path.exists() and not args.force:
        print(f"[skip] {out_path} уже существует, --force чтобы пересоздать")
        return

    if not demo_xml.is_file():
        print(f"Error: эталон не найден: {demo_xml}", file=sys.stderr)
        print("Сначала выгрузите БСП-демо объект.", file=sys.stderr)
        sys.exit(1)

    text = demo_xml.read_text(encoding="utf-8")
    text = rename(text, args.owner_name, args.new_name, args.synonym_owner)
    text = drop_attributes(text, DROP_ATTRIBUTES)
    text = drop_tabular_sections(text)
    text = simplify_composite_types(text, SIMPLIFY_AUTHOR_LIKE)
    text = regen_uuids(text)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    print(f"[ok] {out_path} ({len(text)} байт)")

    if args.register:
        config_xml = src_dir / "Configuration.xml"
        if config_xml.is_file():
            register_in_configuration(config_xml, args.new_name)
            sort_script = Path(__file__).parent.parent.parent / "cf-sort-children" / "scripts" / "cf-sort-children.py"
            if sort_script.is_file():
                print("[sort] cf-sort-children")
                subprocess.run([sys.executable, str(sort_script), str(config_xml)])
        else:
            print(f"[warn] Configuration.xml не найден: {config_xml}")


if __name__ == "__main__":
    main()
