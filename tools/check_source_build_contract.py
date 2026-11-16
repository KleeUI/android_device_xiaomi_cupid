#!/usr/bin/env python3
# Copyright (C) 2026 The KleeUI Project
# SPDX-License-Identifier: Apache-2.0
"""Check source definitions and reject vendor prebuilt overrides for Cupid.

This is a static preflight, not a Make/Soong interpreter or hardware test.
Run it after setup-makefiles.py. Use --module-info after generating the build
graph to additionally check the module owners selected by the build system.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/|'
                   r'[A-Za-z_][A-Za-z_0-9]*|[^\s]')


def bp_modules(text: str) -> list[dict]:
    """Read top-level module blocks, balancing tokens outside comments."""
    tokens = [m.group() for m in TOKEN.finditer(text)
              if not m.group().startswith(("//", "/*"))]
    result = []
    i = 0
    while i + 1 < len(tokens):
        if tokens[i + 1] != "{" or not re.fullmatch(r"\w+", tokens[i]):
            i += 1
            continue
        kind = tokens[i]
        start = i + 2
        i = start
        depth = 1
        properties = {}
        while i < len(tokens) and depth:
            token = tokens[i]
            if depth == 1 and i + 2 < len(tokens) and tokens[i + 1] == ":":
                properties[token] = tokens[i + 2]
            if token in ("{", "["):
                depth += 1
            elif token in ("}", "]"):
                depth -= 1
            i += 1
        raw_name = properties.get("name", "")
        if raw_name.startswith('"'):
            result.append({"type": kind, "name": json.loads(raw_name),
                           "properties": properties,
                           "tokens": tokens[start:i - 1]})
    return result


def make_text(text: str) -> str:
    return re.sub(r"#[^\n]*", "", text).replace("\\\n", " ")


def make_modules(text: str) -> list[dict]:
    result = []
    for block in re.split(r"include\s+\$\(CLEAR_VARS\)", make_text(text)):
        name = re.search(r"^\s*LOCAL_MODULE\s*:?=\s*(\S+)", block, re.M)
        build = re.search(r"include\s+\$\((BUILD_\w+)\)", block)
        if name and build:
            result.append({"name": name[1], "type": build[1],
                           "properties": {}, "text": block})
    return result


def read_modules(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    return bp_modules(text) if path.suffix == ".bp" else make_modules(text)


def has_source(module: dict) -> bool:
    if module["type"] == "cc_library_headers":
        return True
    if module["type"].startswith("BUILD_"):
        return bool(re.search(r"^[ \t]*LOCAL_SRC_FILES[ \t]*[:+]?=[ \t]*\S",
                              module["text"], re.M))
    tokens = module["tokens"]
    # Named source-list expressions are resolved by Soong, not this preflight.
    for i in range(len(tokens) - 3):
        if tokens[i:i + 2] == ["srcs", ":"]:
            if tokens[i + 2:i + 4] == ["[", "]"]:
                return False
            if tokens[i + 2] == "[":
                end = tokens.index("]", i + 3)
                literals = [json.loads(t) for t in tokens[i + 3:end]
                            if t.startswith('"')]
                if any(Path(s).suffix.lower() in (".so", ".a", ".o", ".bin")
                       for s in literals):
                    return False
            return True
    return False


def validate(top: Path, contract: dict, module_info: dict | None = None) -> list[str]:
    errors = []
    definitions = {}
    owners = {}
    for group in contract["source_built"]:
        root = top / group["root"]
        for expected in group.get("modules", []):
            owners[expected["name"]] = (group, expected)
        if not root.is_dir():
            errors.append(f'missing source tree: {group["root"]}')
            continue
        for relative in group.get("required_files", []):
            if not (root / relative).is_file():
                errors.append(f'missing source input: {group["root"]}/{relative}')
        for expected in group.get("modules", []):
            name = expected["name"]
            path = root / expected["file"]
            if not path.is_file():
                errors.append(f'{name}: missing definition {path.relative_to(top)}')
                continue
            if path not in definitions:
                definitions[path] = read_modules(path)
            matches = [m for m in definitions[path] if m["name"] == name]
            if len(matches) != 1:
                errors.append(f'{name}: expected one definition in {path.relative_to(top)}')
                continue
            module = matches[0]
            if module["type"] != expected["type"] or not has_source(module):
                errors.append(f'{name}: expected {expected["type"]} with source inputs, '
                              f'found {module["type"]} in {path.relative_to(top)}')
            if module["properties"].get("enabled") == "false":
                errors.append(f'{name}: source definition is disabled')

    for check in contract.get("product_checks", []):
        path = top / check["file"]
        if not path.is_file():
            errors.append(f'missing product file: {check["file"]}')
            continue
        text = make_text(path.read_text(encoding="utf-8"))
        for name, value in check.get("assignments", {}).items():
            assignments = re.findall(r"^\s*" + re.escape(name)
                                     + r"\s*:?=\s*(.*?)\s*$", text, re.M)
            if not assignments or assignments[-1] != value:
                errors.append(f'{check["file"]}: requires {name} := {value}')
        for token in check.get("contains", []):
            if token not in text:
                errors.append(f'{check["file"]}: missing selection {token}')

    # Source in another namespace alone cannot prevent a vendor prebuilt
    # shadow. Check the normalized vendor metadata as well as definitions.
    for relative in contract.get("vendor_metadata", []):
        path = top / relative
        if not path.is_file():
            errors.append(f'missing normalized vendor metadata: {relative}')
            continue
        for module in read_modules(path):
            if (module["name"] in owners and "prebuilt" in module["type"].lower()
                    and module["properties"].get("enabled") != "false"):
                errors.append(f'{relative}: active prebuilt shadows source {module["name"]}')

    if module_info is not None:
        for name, (group, expected) in owners.items():
            if not expected.get("graph_module", True):
                continue  # Source-only filegroups do not emit Android modules.
            actual = module_info.get(name)
            if not actual:
                errors.append(f'module-info: {name} is absent from the generated graph')
                continue
            paths = actual.get("path", [])
            prefix = group["root"].rstrip("/")
            if not paths or any(p != prefix and not p.startswith(prefix + "/") for p in paths):
                errors.append(f'module-info: {name} has unexpected owner(s): {paths}')
            if expected.get("installed", True) and not actual.get("installed"):
                errors.append(f'module-info: {name} has no installed output')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=Path, required=True, help="full Android checkout root")
    parser.add_argument("--contract", type=Path,
                        default=Path(__file__).resolve().parents[1]
                        / "configs" / "source-build-contract.json")
    parser.add_argument("--module-info", type=Path,
                        help="generated out/target/product/cupid/module-info.json")
    args = parser.parse_args()
    try:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        if contract.get("version") != 1:
            raise ValueError("unsupported source-build contract version")
        module_info = (json.loads(args.module_info.read_text(encoding="utf-8"))
                       if args.module_info else None)
        errors = validate(args.top.resolve(), contract, module_info)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"source-build contract: FAIL\n  {error}")
        return 1
    print("source-build contract: " + ("FAIL" if errors else "OK (static preflight)"))
    for error in errors:
        print(f"  {error}")
    if not errors:
        print(f"  source groups: {len(contract['source_built'])}")
        print("  generated module ownership checked" if module_info is not None
              else "  build graph, compilation and hardware behavior are not verified")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
