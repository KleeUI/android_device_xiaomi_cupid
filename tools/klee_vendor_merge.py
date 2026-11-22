# Copyright (C) 2026 The KleeUI Project
# SPDX-License-Identifier: Apache-2.0

"""Assemble Cupid vendor inputs from separately prepared Klee vendor trees."""

from contextlib import contextmanager
import ctypes
import errno
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
from tempfile import TemporaryDirectory

from .klee_vendor import VendorPreparationError, _sha256, apply_source_patches, apply_vendor_patches


CUPID = "vendor/xiaomi/cupid"
COMMON = "vendor/xiaomi/sm8450-common"
MERGE_RECEIPT = ".klee-vendor-merge.json"
_SCHEMA = 1
_METADATA = ("Android.bp", "cupid-vendor.mk", "sm8450-common-vendor.mk")
_OPTIONAL_METADATA = ("Android.mk", "BoardConfigVendor.mk")
_WFD = "proprietary/system/framework/WfdCommon.jar"
_WFD_GROUP = "cupid_wfd_common_jar"
_C2AUDIO_MODULE = "vendor.qti.media.c2audio@1.0-service"
_C2AUDIO_SOURCE = "compat/c2audio-service/service.cpp"
_C2AUDIO_HEADER = "compat/c2audio-service/qc2_factory_abi.h"
_IMPORTS = ("vendor/qcom/opensource/agm", "vendor/qcom/opensource/pal")
_NAMESPACE = re.compile(r"(?m)^soong_namespace\s*\{([^{}]*)\}[ \t]*\n?")
_MODULE_NAME = re.compile(r'^    name:\s*"([^"\n]+)"\s*,', re.MULTILINE)
_COPY_LINE = re.compile(r"^[ \t]+(vendor/xiaomi/[^\s]+:[^\s]+)[ \t]+\\[ \t]*\n$")


def _plain_directory(path):
    return path.is_dir() and not path.is_symlink() and path.resolve() == path


def _plain_file(path):
    return path.is_file() and not path.is_symlink() and path.resolve() == path


def _related(first, second):
    return first == second or first in second.parents or second in first.parents


def _record(path):
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode):
        return ["symlink", os.readlink(path)]
    if stat.S_ISDIR(mode):
        return ["directory", stat.S_IMODE(mode)]
    if stat.S_ISREG(mode):
        return ["file", stat.S_IMODE(mode), _sha256(path).hex()]
    raise VendorPreparationError(f"Unsupported vendor input type: {path}")


def _inventory(root):
    entries = {}

    def visit(directory):
        for path in sorted(directory.iterdir()):
            if directory == root and path.name == MERGE_RECEIPT:
                continue
            key = path.relative_to(root).as_posix()
            item = entries[key] = _record(path)
            if item[0] == "directory":
                visit(path)

    visit(root)
    return entries


def _copy_tree(source, destination):
    created = not os.path.lexists(destination)
    if created:
        destination.mkdir()
    elif not _plain_directory(destination):
        raise VendorPreparationError(f"Vendor input directory collision: {destination}")
    for path in sorted(source.iterdir()):
        target = destination / path.name
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            _copy_tree(path, target)
        elif not (stat.S_ISREG(mode) or stat.S_ISLNK(mode)):
            raise VendorPreparationError(f"Unsupported vendor input type: {path}")
        elif not os.path.lexists(target):
            shutil.copy2(path, target, follow_symlinks=False)
        else:
            item = _record(path)
            prior = _record(target)
            # Identical file bytes share the first owner's mode and timestamps.
            identical = item == prior or item[0] == prior[0] == "file" and item[2] == prior[2]
            if not identical:
                raise VendorPreparationError(f"Vendor input collision for {path} and {target}")
    if created:
        shutil.copystat(source, destination)


def _read_metadata(path):
    if not _plain_file(path):
        raise VendorPreparationError(f"Missing vendor build metadata: {path}")
    return path.read_text(encoding="utf-8")


def _namespace(content):
    found = list(_NAMESPACE.finditer(content))
    if len(found) != 1:
        raise VendorPreparationError("Expected one generated Soong namespace per prepared vendor tree")
    body = re.sub(r"//[^\n]*", "", found[0][1]).strip()
    if not body:
        return found[0], []
    imports = re.fullmatch(r"imports:\s*\[(.*?)\]\s*,?", body, re.DOTALL)
    if imports is None:
        raise VendorPreparationError("Unexpected properties in prepared vendor Soong namespace")
    return found[0], [json.loads(item) for item in re.findall(r'"[^"\n]+"', imports[1])]


def _merge_blueprints(cupid, common):
    cupid = _read_metadata(cupid / "Android.bp")
    common = _read_metadata(common / "Android.bp")
    cup_namespace, cup_imports = _namespace(cupid)
    common_namespace, common_imports = _namespace(common)
    source_module = re.search(r'(?ms)^cc_binary\s*\{\s*name:\s*"'
                              + re.escape(_C2AUDIO_MODULE) + r'"\s*,(.*?)^\}', common)
    if source_module is None or f'"{_C2AUDIO_SOURCE}"' not in source_module[1]:
        raise VendorPreparationError("Prepared common vendor metadata must include the Klee source C2 audio launcher")
    imports = sorted((set(cup_imports) | set(common_imports) | set(_IMPORTS)) - {CUPID, COMMON})
    namespace = "soong_namespace {\n    imports: [\n"
    namespace += "".join(f"        {json.dumps(path)},\n" for path in imports)
    namespace += "    ],\n}\n"
    modules = cupid[:cup_namespace.start()] + namespace + cupid[cup_namespace.end():]
    modules += "\n" + common[common_namespace.end():].lstrip()
    modules = modules.replace(COMMON, CUPID)

    names = set()
    for name in _MODULE_NAME.findall(modules):
        if name in names:
            raise VendorPreparationError(f"Duplicate Soong module in merged vendor inputs: {name}")
        names.add(name)
    if _WFD_GROUP in names or "WfdCommon" in names:
        raise VendorPreparationError("Prepared vendor metadata already defines a WFD framework jar module")
    return (modules.rstrip() + f'\n\nfilegroup {{\n    name: "{_WFD_GROUP}",\n'
            f'    srcs: ["{_WFD}"],\n    visibility: ["//device/xiaomi/cupid:__pkg__"],\n}}\n')


def _make_fragments(cupid, common):
    common_text = _read_metadata(common / "sm8450-common-vendor.mk").replace(COMMON, CUPID)
    cupid_text = _read_metadata(cupid / "cupid-vendor.mk").replace(COMMON, CUPID)
    namespace = re.compile(r"(?m)^PRODUCT_SOONG_NAMESPACES\s*\+=\s*\\?[ \t\n]+" + re.escape(CUPID) + r"[ \t]*\n")
    if len(namespace.findall(common_text)) != 1 or len(namespace.findall(cupid_text)) != 1:
        raise VendorPreparationError("Unexpected PRODUCT_SOONG_NAMESPACES in prepared vendor metadata")
    cupid_text = namespace.sub("", cupid_text, count=1)

    # The common fragment is inherited first. Suppress only literally identical
    # copy rules after rebasing, so existing precedence with Klee stays intact.
    # Leave terminal rules in place to preserve their Make continuation block.
    common_rules = {match[1] for line in common_text.splitlines(keepends=True) if (match := _COPY_LINE.match(line))}
    cupid_lines = []
    for line in cupid_text.splitlines(keepends=True):
        match = _COPY_LINE.match(line)
        if match is None or match[1] not in common_rules:
            cupid_lines.append(line)
    return "".join(cupid_lines), common_text


def _build_candidate(cupid, common, stage):
    for tree in (cupid, common):
        source = tree / "proprietary"
        if not _plain_directory(source):
            raise VendorPreparationError(f"Missing prepared proprietary directory: {source}")
        _copy_tree(source, stage / "proprietary")
        compat = tree / "compat"
        if os.path.lexists(compat):
            if not _plain_directory(compat):
                raise VendorPreparationError(f"Invalid vendor compatibility source directory: {compat}")
            _copy_tree(compat, stage / "compat")

    makefiles = dict(zip(_METADATA[1:], _make_fragments(cupid, common)))
    metadata = {"Android.bp": _merge_blueprints(cupid, common), **makefiles}
    for name in _OPTIONAL_METADATA:
        for tree in (cupid, common):
            if os.path.lexists(tree / name):
                content = _read_metadata(tree / name).replace(COMMON, CUPID)
                if name in metadata and metadata[name] != content:
                    raise VendorPreparationError(f"Colliding vendor build metadata: {name}")
                metadata[name] = content

    required = set(re.findall(r'"((?:proprietary|compat)/[^"\n]+)"', metadata["Android.bp"]))
    required.add(_C2AUDIO_HEADER)
    for content in makefiles.values():
        required.update(re.findall(re.escape(CUPID) + r"/([^\s:$)\\]+):", content))
    for name in sorted(required):
        path = stage / name
        if not path.is_file() or stage not in path.resolve().parents:
            raise VendorPreparationError(f"Missing required vendor input: {name}")
    for name, content in metadata.items():
        (stage / name).write_bytes(content.encode("utf-8"))


def _owned_inventory(destination):
    marker = destination / MERGE_RECEIPT
    if not _plain_directory(destination) or not _plain_file(marker):
        raise VendorPreparationError(f"Preserve the existing vendor tree before replacing it: {destination}")
    try:
        receipt = json.loads(marker.read_bytes())
        entries = receipt["entries"]
        if receipt["schema"] == _SCHEMA and isinstance(entries, dict):
            return entries
    except (ValueError, KeyError, TypeError):
        pass
    raise VendorPreparationError(f"Invalid vendor merge receipt: {marker}")


def check_merged_vendor(top: Path) -> list[tuple[str, str]]:
    """Check the merged vendor build metadata without hashing the blob tree."""
    top = top.resolve()
    if os.path.lexists(top / COMMON):
        raise VendorPreparationError(f"The separate vendor tree still exists: {top / COMMON}")
    destination = top / CUPID
    entries = _owned_inventory(destination)
    checked = list(_METADATA) + [name for name in _OPTIONAL_METADATA if name in entries]
    for name in checked:
        path = destination / name
        if not _plain_file(path) or _record(path) != entries.get(name):
            raise VendorPreparationError(f"Merged vendor metadata has changed: {path}")
    for name in set(_OPTIONAL_METADATA) - set(checked):
        path = destination / name
        if os.path.lexists(path):
            raise VendorPreparationError(f"Unexpected merged vendor build metadata: {path}")
    for name in (_WFD, _C2AUDIO_SOURCE, _C2AUDIO_HEADER):
        path = destination / name
        if not path.is_file() or destination not in path.resolve().parents:
            raise VendorPreparationError(f"Missing required merged vendor input: {path}")
    return [(CUPID, "merged")]


def prepare_vendor_tree(
    top: Path, device_dir: Path, *, check_only: bool = False
) -> list[tuple[str, str]]:
    if os.path.lexists(top / CUPID / MERGE_RECEIPT):
        return check_merged_vendor(top) + apply_source_patches(top, device_dir, check_only=check_only)
    return apply_vendor_patches(top, device_dir, check_only=check_only)


@contextmanager
def _merge_lock(parent):
    with (parent / ".klee-cupid-vendor.lock").open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def _publish_tree(stage, destination, *, replace):
    if not sys.platform.startswith("linux"):
        if replace:
            raise VendorPreparationError("Replacing an existing merged vendor tree requires Linux atomic directory exchange")
        stage.rename(destination)
        return
    rename = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if rename is None:
        raise VendorPreparationError("This Linux environment lacks atomic vendor directory publication")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    # Linux renameat2 uses AT_FDCWD for absolute paths. Do not overwrite a
    # destination that appeared after our ownership check on the first run.
    rename_flag = 2 if replace else 1  # RENAME_EXCHANGE or RENAME_NOREPLACE
    if rename(-100, os.fsencode(stage), -100, os.fsencode(destination), rename_flag) != 0:
        error = ctypes.get_errno()
        if error in {errno.EINVAL, errno.ENOSYS, errno.ENOTSUP}:
            raise VendorPreparationError("This filesystem does not support atomic vendor directory publication")
        raise OSError(error, os.strerror(error), str(destination))


def merge_vendor_inputs(top: Path, prepared_root: Path, device_dir: Path) -> list[tuple[str, str]]:
    """Publish a single vendor tree from the normalized Cupid and common inputs."""
    top = top.resolve()
    prepared_root = prepared_root.resolve()
    destination = top / CUPID
    cupid, common = prepared_root / CUPID, prepared_root / COMMON
    if any(_related(source, destination) for source in (cupid, common)):
        raise VendorPreparationError(f"Pass a separate prepared vendor root to {device_dir / 'extract-files.py'}")
    for tree in (cupid, common):
        if not _plain_directory(tree) or os.path.lexists(tree / MERGE_RECEIPT):
            raise VendorPreparationError(f"Expected a separate normalized vendor input tree: {tree}")

    parent = destination.parent
    if parent.resolve() != parent:
        raise VendorPreparationError(f"Invalid destination parent: {parent}")
    parent.mkdir(parents=True, exist_ok=True)
    with _merge_lock(parent):
        if os.path.lexists(top / COMMON):
            raise VendorPreparationError(f"The separate vendor tree still exists: {top / COMMON}")
        previous = None
        if os.path.lexists(destination):
            previous = _owned_inventory(destination)
            if _inventory(destination) != previous:
                raise VendorPreparationError(f"Existing merged vendor files have been edited: {destination}")

        with TemporaryDirectory(dir=parent, prefix=".klee-cupid-vendor-") as directory:
            workspace = Path(directory)
            # Soong may scan the source tree while we prepare its successor.
            (workspace / ".find-ignore").touch()
            stage = workspace / "tree"
            stage.mkdir()
            _build_candidate(cupid, common, stage)
            entries = _inventory(stage)
            if previous == entries:
                return [(CUPID, "unchanged")]
            receipt = {"schema": _SCHEMA, "entries": entries}
            (stage / MERGE_RECEIPT).write_bytes((json.dumps(receipt, sort_keys=True) + "\n").encode("utf-8"))
            if previous is None and os.path.lexists(destination):
                raise VendorPreparationError(f"The vendor destination appeared during preparation: {destination}")
            if previous is not None:
                if _owned_inventory(destination) != previous or _inventory(destination) != previous:
                    raise VendorPreparationError(f"The vendor destination changed during preparation: {destination}")
            _publish_tree(stage, destination, replace=previous is not None)
    return [(CUPID, "updated")]
