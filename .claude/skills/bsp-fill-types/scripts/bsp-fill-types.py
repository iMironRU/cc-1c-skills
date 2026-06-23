#!/usr/bin/env python3
"""Fill BSP defined types with configuration object references after MergeCfg.

Generalized from chronicon/scripts/post-merge-defined-types.py — reads mapping
from JSON file instead of hardcoded object names.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '_lib'))
from v8_platform import find_project_root

PLACEHOLDER_PAT = re.compile(
    r'<Type>\s*<v8:Type>xs:string</v8:Type>\s*<v8:StringQualifiers>.*?</v8:StringQualifiers>\s*</Type>',
    re.DOTALL,
)


def fill_defined_type(xml_path, types_to_add):
    src = xml_path.read_text(encoding="utf-8")
    type_block = re.search(r'<Type>(.*?)</Type>', src, re.DOTALL)
    if not type_block:
        print(f"[skip] {xml_path.name}: нет <Type>", file=sys.stderr)
        return False

    body = type_block.group(1)
    existing_types = set(re.findall(r'<v8:Type>([^<]+)</v8:Type>', body))
    to_add = [t for t in types_to_add if t not in existing_types]

    if not to_add and "xs:string" not in existing_types:
        print(f"[skip] {xml_path.stem}: уже заполнен ({len(existing_types)} типов)")
        return False

    if PLACEHOLDER_PAT.search(src):
        new_block = "<Type>\n" + "\n".join(
            f"\t\t\t\t<v8:Type>{t}</v8:Type>" for t in types_to_add
        ) + "\n\t\t\t</Type>"
        new_src = PLACEHOLDER_PAT.sub(new_block, src, count=1)
        action = f"replace-placeholder ({len(types_to_add)} типов)"
    else:
        new_types_xml = "\n".join(
            f"\t\t\t\t<v8:Type>{t}</v8:Type>" for t in to_add
        )
        new_src = src.replace("</Type>", f"{new_types_xml}\n\t\t\t</Type>", 1)
        action = f"append ({len(to_add)} типов)"

    xml_path.write_text(new_src, encoding="utf-8")
    print(f"[ok] {xml_path.stem}: {action}")
    return True


def main():
    p = argparse.ArgumentParser(description="Fill BSP defined types from JSON mapping")
    p.add_argument("--types-map", required=True, help="JSON file: {TypeName: [type1, type2]}")
    p.add_argument("--unpack-dir", default="", help="Unpacked config dir (default: base/bsp-merged-unpack)")
    args = p.parse_args()

    with open(args.types_map, encoding="utf-8") as f:
        fill_map = json.load(f)

    unpack_dir = Path(args.unpack_dir) if args.unpack_dir else None
    if not unpack_dir:
        root = find_project_root() or os.getcwd()
        unpack_dir = Path(root) / "base/bsp-merged-unpack"

    dt_dir = unpack_dir / "DefinedTypes"
    if not dt_dir.is_dir():
        print(f"Error: нет директории: {dt_dir}", file=sys.stderr)
        sys.exit(1)

    changed = 0
    missing = []
    for name, types in fill_map.items():
        xml = dt_dir / f"{name}.xml"
        if not xml.is_file():
            missing.append(name)
            continue
        if fill_defined_type(xml, types):
            changed += 1

    print(f"\n[summary] изменено: {changed}/{len(fill_map)}")
    if missing:
        print(f"[warn] не найдены опр.типы: {', '.join(missing)}", file=sys.stderr)
    sys.exit(0 if not missing else 1)


if __name__ == "__main__":
    main()
