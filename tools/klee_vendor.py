#!/usr/bin/env python3
#
# Copyright (C) 2026 The KleeUI Project
#
# SPDX-License-Identifier: Apache-2.0
#

"""Small, AOSP-only helpers for Cupid proprietary inputs.

This module is intentionally independent of LineageOS extract_utils.  It only
copies the device inventory and normalizes already-populated vendor metadata.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from typing import Iterable


PATCH_NAMES = (
    "0001-sm8450-common-adapt-generated-metadata-for-klee.patch",
    "0002-sm8450-common-keep-WfdCommon-off-bootclasspath.patch",
    "0003-cupid-drop-lineage-soong-imports.patch",
    "0004-cupid-install-klee-stock-delta-files.patch",
    "0005-sm8450-common-prefer-open-location-libraries.patch",
    "0006-sm8450-common-select-source-audio-runtime.patch",
    "0007-sm8450-common-select-source-location-base-util.patch",
    "0009-sm8450-common-restore-stock-location-base-util.patch",
    "0010-sm8450-common-prefer-source-location-adapters.patch",
    "0011-sm8450-common-disable-duplicate-location-prebuilts.patch",
    "0012-sm8450-common-source-location-module-ownership.patch",
    "0014-sm8450-common-source-gnsspps-module-ownership.patch",
)

# The manifest pins the Klee location and AudioReach forks with their complete
# Soong adapters. Keep those source integrations out of the generated-vendor
# metadata stack; applying historical 0013 again would change their namespace.
# Independent source fixes may already be applied to an existing full checkout.
NFC_BASELINE_PATCH = "0016-waipio-nfc-align-driver-baseline.patch"
NFC_FIX_PATCH = "0017-waipio-nfc-cancel-reads-and-serialize-ese-responses.patch"
SOURCE_PATCH_NAMES = (
    "0015-libvmmem-use-size-t-format.patch",
    NFC_FIX_PATCH,
)

REQUIRED_VENDOR_FILES = (
    "vendor/xiaomi/cupid/Android.bp",
    "vendor/xiaomi/cupid/cupid-vendor.mk",
    "vendor/xiaomi/sm8450-common/Android.bp",
    "vendor/xiaomi/sm8450-common/sm8450-common-vendor.mk",
)

# The reviewed R6 launcher is an independent overlay, not generated metadata.
# Match the entire module (apart from a uniform LF/CRLF choice) before projecting
# it inside an isolated patch workspace. Never put this prebuilt back in TOP.
_C2AUDIO_METADATA = "vendor/xiaomi/sm8450-common/Android.bp"
_C2AUDIO_SOURCE_SHA256 = "f84dd4e42c9d4a285423f4552314aae15a0ffd94fe4d230ce5c91e2b2e027dd9"
_C2AUDIO_PREBUILT = b'''cc_prebuilt_binary {
    name: "vendor.qti.media.c2audio@1.0-service",
    owner: "xiaomi",
    target: {
        android_arm64: {
            srcs: [
                "proprietary/vendor/bin/hw/vendor.qti.media.c2audio@1.0-service",
            ],
            shared_libs: [
                "libutils",
                "libcutils",
                "liblog",
                "libcodec2_vndk",
                "libqc2audio_base",
                "libqc2audio_utils",
                "libqc2audio_basecodec",
                "libqc2audio_platform",
                "libqc2audio_core",
                "libqdMetaData",
                "android.hardware.media.c2@1.0",
                "libavservices_minijail",
                "libbinder",
                "libhidlbase",
                "libhidltransport",
                "libhwbinder",
                "libvndksupport",
                "libcodec2_hidl@1.0",
                "libc++",
                "libc",
                "libm",
                "libdl",
            ],
        },
    },
    compile_multilib: "64",
    strip: {
        none: true,
    },
    prefer: true,
    relative_install_path: "hw",
    soc_specific: true,
}
'''
_C2AUDIO_SOURCE_FILES = (
    "vendor/xiaomi/sm8450-common/compat/c2audio-service/service.cpp",
    "vendor/xiaomi/sm8450-common/compat/c2audio-service/qc2_factory_abi.h",
)


class VendorPreparationError(RuntimeError):
    """Raised when the local vendor inputs cannot be normalized safely."""


def _c2audio_source_overlay(generated: bytes) -> bytes | None:
    """Recognize only the reviewed source module, rejecting other C2 drift."""
    names = list(re.finditer(
        rb'\bname\s*:\s*"vendor\.qti\.media\.c2audio@1\.0-service"', generated
    ))
    source_references = generated.count(b'"compat/c2audio-service/')
    if not names:
        if source_references:
            raise VendorPreparationError("C2 audio source module has unrecognized drift")
        return None
    if len(names) != 1:
        raise VendorPreparationError("C2 audio module is duplicated or has drift")
    name = names[0]
    starts = list(re.finditer(
        rb"(?m)^[a-z_][a-z0-9_]*[ \t]*\{[ \t]*\r?$", generated[:name.start()]
    ))
    end = re.search(rb"(?m)^\}\r?\n", generated[name.end():])
    if not starts or end is None:
        raise VendorPreparationError("C2 audio module has drift")
    block = generated[starts[-1].start():name.end() + end.end()]
    normalized = block.replace(b"\r\n", b"\n")
    if block not in (normalized, normalized.replace(b"\n", b"\r\n")):
        raise VendorPreparationError("C2 audio module has mixed line endings")
    if normalized == _C2AUDIO_PREBUILT:
        if source_references:
            raise VendorPreparationError("C2 audio source module is duplicated or has drift")
        return None
    if hashlib.sha256(normalized).hexdigest() != _C2AUDIO_SOURCE_SHA256:
        raise VendorPreparationError("C2 audio source module has unrecognized drift")
    if source_references != 1:
        raise VendorPreparationError("C2 audio source module is duplicated or has drift")
    return block


def _apply_with_c2audio_overlay(
    top: Path, device_dir: Path, overlay: bytes, *, check_only: bool
) -> list[tuple[str, str]]:
    """Run the unchanged strict patch checks on an isolated projected copy."""
    missing = [path for path in _C2AUDIO_SOURCE_FILES
               if not (top / path).is_file() or not (top / path).stat().st_size]
    if missing:
        raise VendorPreparationError(
            "C2 audio source overlay is missing its source inputs:\n  "
            + "\n  ".join(missing)
        )
    paths = set(REQUIRED_VENDOR_FILES) | _patch_target_paths(
        device_dir, PATCH_NAMES + _source_patch_files()
    )
    with tempfile.TemporaryDirectory(prefix="klee-vendor-c2audio-") as directory:
        projected = Path(directory)
        original: dict[str, bytes | None] = {}
        for relative in paths:
            source = top / relative
            destination = projected / relative
            if source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                original[relative] = source.read_bytes()
            else:
                original[relative] = None
        generated = projected / _C2AUDIO_METADATA
        generated.write_bytes(generated.read_bytes().replace(overlay, _C2AUDIO_PREBUILT, 1))
        # The recursive call sees the exact canonical prebuilt, so it executes
        # all existing forward/reverse, prefix, source and filegroup checks.
        results = apply_vendor_patches(projected, device_dir, check_only=check_only)
        if check_only:
            return results + [("c2audio-source-overlay", "preserved")]
        content = generated.read_bytes()
        if content.count(_C2AUDIO_PREBUILT) != 1:
            raise VendorPreparationError("metadata patches changed the C2 audio baseline")
        generated.write_bytes(content.replace(_C2AUDIO_PREBUILT, overlay, 1))
        if _c2audio_source_overlay(generated.read_bytes()) != overlay:
            raise VendorPreparationError("C2 audio source overlay was not restored")

        # Validate every input again before the first persistent write. Only
        # actual metadata/source patch targets can leave this private workspace.
        changes: list[tuple[Path, bytes]] = []
        for relative, before in original.items():
            destination = top / relative
            current = destination.read_bytes() if destination.is_file() else None
            if current != before:
                raise VendorPreparationError("vendor inputs changed during normalization")
            candidate = projected / relative
            after = candidate.read_bytes() if candidate.is_file() else None
            if after != before:
                if after is None:
                    raise VendorPreparationError("metadata patches unexpectedly deleted an input")
                changes.append((destination, after))
        for destination, after in changes:
            destination.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".klee-vendor-", dir=destination.parent
            )
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                temporary.write_bytes(after)
                if destination.exists():
                    # Changed content must keep a fresh mtime for incremental builds.
                    shutil.copymode(destination, temporary)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        return results + [("c2audio-source-overlay", "preserved")]


def find_android_root(start: Path) -> Path:
    """Return the nearest parent that looks like an initialized AOSP tree."""
    for candidate in (start.resolve(), *start.resolve().parents):
        if (candidate / "build" / "envsetup.sh").is_file():
            return candidate
    raise VendorPreparationError(
        "cannot find Android root; pass --top pointing at the AOSP checkout"
    )


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def _apply_patch(
    top: Path, patch_file: Path, *, reverse: bool
) -> subprocess.CompletedProcess[str]:
    command = [
        "patch",
        "-p1",
        "--batch",
        "--fuzz=0",
        "--reverse" if reverse else "--forward",
        f"--input={patch_file}",
    ]
    return _run(command, top)


def _source_patch_files() -> tuple[str, ...]:
    if NFC_FIX_PATCH in SOURCE_PATCH_NAMES:
        return (*SOURCE_PATCH_NAMES, NFC_BASELINE_PATCH)
    return SOURCE_PATCH_NAMES


def _nfc_source_patches(top: Path, device_dir: Path) -> tuple[str, ...]:
    fix = (NFC_FIX_PATCH,)
    stack = (NFC_BASELINE_PATCH, NFC_FIX_PATCH)
    matching = [
        pending
        for patches, reverse, pending in ((stack, False, stack), (fix, False, fix), (fix, True, ()))
        if _probe_patch_stack(top, device_dir, reverse=reverse, patch_names=patches)
    ]
    if len(matching) == 1:
        return matching[0]
    raise VendorPreparationError(
        f"source compatibility patch is ambiguous or has drift: {NFC_FIX_PATCH}"
    )


def _patch_target_paths(
    device_dir: Path, patch_names: tuple[str, ...] | None = None
) -> set[str]:
    """Collect every repository path touched by the metadata patch stack."""
    if patch_names is None:
        patch_names = PATCH_NAMES
    paths: set[str] = set()
    for name in patch_names:
        patch_file = device_dir / "patches" / name
        for raw in patch_file.read_text(encoding="utf-8").splitlines():
            if raw.startswith("--- ") or raw.startswith("+++ "):
                path = raw[4:].split("\t", 1)[0]
                if path == "/dev/null":
                    continue
                if path.startswith("a/") or path.startswith("b/"):
                    paths.add(path[2:])
    return paths


def _probe_patch_stack(
    top: Path,
    device_dir: Path,
    *,
    reverse: bool,
    patch_names: tuple[str, ...] | None = None,
) -> bool:
    """Apply and undo the complete patch stack in an isolated vendor tree."""
    if patch_names is None:
        patch_names = PATCH_NAMES
    with tempfile.TemporaryDirectory(prefix="klee-vendor-patches-") as directory:
        probe_top = Path(directory)
        original: dict[str, bytes | None] = {}
        target_paths = set(REQUIRED_VENDOR_FILES) | _patch_target_paths(
            device_dir, patch_names
        )
        for relative in target_paths:
            source = top / relative
            destination = probe_top / relative
            if source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                original[relative] = source.read_bytes()
            else:
                original[relative] = None

        ordered_names = tuple(reversed(patch_names)) if reverse else patch_names
        for name in ordered_names:
            result = _apply_patch(
                probe_top, device_dir / "patches" / name, reverse=reverse
            )
            if result.returncode:
                return False

        undo_names = patch_names if reverse else tuple(reversed(patch_names))
        for name in undo_names:
            result = _apply_patch(
                probe_top, device_dir / "patches" / name, reverse=not reverse
            )
            if result.returncode:
                return False

        for relative, content in original.items():
            candidate = probe_top / relative
            if content is None:
                if candidate.exists():
                    return False
            elif not candidate.is_file() or candidate.read_bytes() != content:
                return False
        return True


def _probe_applied_prefix(top: Path, device_dir: Path, count: int) -> bool:
    """Validate an older normalized vendor stack without changing its input."""
    with tempfile.TemporaryDirectory(prefix="klee-vendor-prefix-") as directory:
        probe_top = Path(directory)
        original: dict[str, bytes | None] = {}
        for relative in set(REQUIRED_VENDOR_FILES) | _patch_target_paths(device_dir):
            source = top / relative
            destination = probe_top / relative
            if source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                original[relative] = source.read_bytes()
            else:
                original[relative] = None

        prefix = PATCH_NAMES[:count]
        # Undo the candidate prefix, validate the current stack in both
        # directions, then restore the original input verbatim. Unrelated
        # generated metadata is deliberately preserved by each round trip.
        operations = (
            (tuple(reversed(prefix)), True),
            (PATCH_NAMES, False),
            (tuple(reversed(PATCH_NAMES)), True),
            (prefix, False),
        )
        for names, reverse in operations:
            for name in names:
                result = _apply_patch(
                    probe_top, device_dir / "patches" / name, reverse=reverse
                )
                if result.returncode:
                    return False

        for relative, content in original.items():
            candidate = probe_top / relative
            if content is None:
                if candidate.exists():
                    return False
            elif not candidate.is_file() or candidate.read_bytes() != content:
                return False
        return True


def _normalize_audio_filegroup(top: Path, *, check_only: bool) -> tuple[str, str]:
    """Drop the obsolete wrapper blob reference after the source migration."""
    vendor = top / "vendor/xiaomi/cupid"
    generated = vendor / "Android.bp"
    block = (
        'filegroup {\n'
        '    name: "cupid_audioadsprpcd_blob",\n'
        '    srcs: ["proprietary/vendor/bin/audioadsprpcd"],\n'
        '    visibility: ["//device/xiaomi/cupid"],\n'
        '}\n'
    )
    generated_bytes = generated.read_bytes()
    generated_text = generated_bytes.decode("utf-8")
    module_names = re.findall(r'\bname\s*:\s*"cupid_audioadsprpcd_blob"', generated_text)
    if not module_names:
        return ("cupid_audioadsprpcd_blob", "already-absent")
    blocks = (block.encode("utf-8"), block.replace("\n", "\r\n").encode("utf-8"))
    matches = [candidate for candidate in blocks if candidate in generated_bytes]
    if len(module_names) != 1 or sum(generated_bytes.count(candidate) for candidate in blocks) != 1:
        raise VendorPreparationError("audio filegroup in generated metadata has drift")
    if check_only:
        return ("cupid_audioadsprpcd_blob", "pending-removal")
    generated.write_bytes(generated_bytes.replace(matches[0], b""))
    return ("cupid_audioadsprpcd_blob", "removed")


def apply_vendor_patches(
    top: Path, device_dir: Path, *, check_only: bool = False
) -> list[tuple[str, str]]:
    """Apply Klee metadata patches once, or verify their current state.

    Several patches modify the same generated file, so probing each patch in
    isolation misclassifies both pristine and fully normalized trees.  Probe
    the complete stack in temporary copies. Accept pristine metadata, a fully
    normalized tree, or a reversible prefix of the current stack. Independently
    preflight source compatibility fixes before changing any persistent input.
    """
    missing = [path for path in REQUIRED_VENDOR_FILES if not (top / path).is_file()]
    if missing:
        raise VendorPreparationError(
            "vendor input is incomplete:\n  " + "\n  ".join(missing)
        )

    for name in PATCH_NAMES + _source_patch_files():
        patch_file = device_dir / "patches" / name
        if not patch_file.is_file():
            raise VendorPreparationError(f"missing metadata patch: {patch_file}")

    overlay = _c2audio_source_overlay((top / _C2AUDIO_METADATA).read_bytes())
    if overlay is not None:
        return _apply_with_c2audio_overlay(
            top, device_dir, overlay, check_only=check_only
        )

    forward = _probe_patch_stack(top, device_dir, reverse=False)
    reverse = _probe_patch_stack(top, device_dir, reverse=True)
    applied_count: int | None = None
    if forward and not reverse:
        applied_count = 0
    elif reverse and not forward:
        applied_count = len(PATCH_NAMES)
    elif not forward and not reverse:
        matches = [
            count
            for count in range(1, len(PATCH_NAMES))
            if _probe_applied_prefix(top, device_dir, count)
        ]
        if matches:
            # Historical patches can cancel one another (0007 and 0009), so
            # several prefixes may produce the same metadata. Every match
            # reaches the same full stack and restores this input byte for
            # byte; resume from the longest valid prefix.
            applied_count = max(matches)
    if applied_count is None:
        state = "both directions match" if forward else "neither direction matches"
        raise VendorPreparationError(
            f"vendor patch stack is ambiguous or has drift: {state}; "
            "regenerate vendor metadata or review the tree manually"
        )

    source_states: list[tuple[str, tuple[str, ...]]] = []
    for name in SOURCE_PATCH_NAMES:
        if name == NFC_FIX_PATCH:
            source_states.append((name, _nfc_source_patches(top, device_dir)))
            continue
        pending = _probe_patch_stack(top, device_dir, reverse=False, patch_names=(name,))
        applied = _probe_patch_stack(
            top, device_dir, reverse=True, patch_names=(name,)
        )
        if pending == applied:
            raise VendorPreparationError(
                f"source compatibility patch has drift or missing input: {name}"
            )
        source_states.append((name, (name,) if pending else ()))

    # Preflight the independent filegroup before any persistent writes as well.
    _normalize_audio_filegroup(top, check_only=True)

    results: list[tuple[str, str]] = []
    for index, name in enumerate(PATCH_NAMES):
        if index < applied_count:
            results.append((name, "already-applied"))
            continue
        if check_only:
            results.append((name, "pending"))
            continue
        patch_file = device_dir / "patches" / name
        result = _apply_patch(top, patch_file, reverse=False)
        if result.returncode:
            raise VendorPreparationError(
                f"failed to apply {name}:\n{result.stdout.rstrip()}"
            )
        results.append((name, "applied"))
    for name, pending in source_states:
        if not pending:
            results.append((name, "already-applied"))
        elif check_only:
            results.append((name, "pending"))
        else:
            for patch_file in pending:
                result = _apply_patch(top, device_dir / "patches" / patch_file, reverse=False)
                if result.returncode:
                    raise VendorPreparationError(
                        f"failed to apply {patch_file}:\n{result.stdout.rstrip()}"
                    )
            results.append((name, "applied"))
    results.append(_normalize_audio_filegroup(top, check_only=check_only))
    return results


def _inventory_path(text: str) -> PurePosixPath:
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise VendorPreparationError(f"unsafe inventory path: {text!r}")
    return path


def read_inventory(inventory: Path) -> list[tuple[PurePosixPath, PurePosixPath]]:
    """Read the small Klee inventory without interpreting generator flags."""
    entries: list[tuple[PurePosixPath, PurePosixPath]] = []
    for number, raw in enumerate(inventory.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Klee only needs the path portion.  A leading '-' marks an
        # extract-only dependency in conventional inventories.
        line = line.split(";", 1)[0]
        if line.startswith("-"):
            line = line[1:]
        source_text, separator, destination_text = line.partition(":")
        source = _inventory_path(source_text)
        destination = _inventory_path(destination_text if separator else source_text)
        entries.append((source, destination))
    if not entries:
        raise VendorPreparationError(f"empty proprietary inventory: {inventory}")
    return entries


def _sha256(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.digest()


def _replace_if_changed(temporary: Path, destination: Path) -> str:
    if destination.is_file() and _sha256(temporary) == _sha256(destination):
        temporary.unlink()
        return "unchanged"
    os.replace(temporary, destination)
    return "updated"


def extract_inventory(
    top: Path,
    device_dir: Path,
    *,
    source_root: Path | None,
    adb: str,
    serial: str | None,
) -> list[tuple[str, str]]:
    """Copy inventory files atomically from a mounted tree or one ADB device."""
    entries = read_inventory(device_dir / "proprietary-files.txt")
    output_root = top / "vendor" / "xiaomi" / "cupid" / "proprietary"
    results: list[tuple[str, str]] = []

    if source_root is None:
        state_command = [adb]
        if serial:
            state_command += ["-s", serial]
        state = subprocess.run(
            state_command + ["get-state"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if state.returncode or state.stdout.strip() != "device":
            raise VendorPreparationError("ADB target is not in device state")

    for source, destination in entries:
        output = output_root.joinpath(*destination.parts)
        output.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output.name}.", dir=output.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            if source_root is not None:
                mounted = source_root.joinpath(*source.parts)
                if not mounted.is_file():
                    raise VendorPreparationError(f"missing source blob: {mounted}")
                shutil.copy2(mounted, temporary)
            else:
                command = [adb]
                if serial:
                    command += ["-s", serial]
                command += ["pull", f"/{source.as_posix()}", str(temporary)]
                result = subprocess.run(
                    command,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                if result.returncode:
                    raise VendorPreparationError(
                        f"failed to pull /{source.as_posix()}:\n"
                        f"{result.stdout.rstrip()}"
                    )
            state = _replace_if_changed(temporary, output)
            results.append((destination.as_posix(), state))
        finally:
            temporary.unlink(missing_ok=True)
    return results


def print_results(results: Iterable[tuple[str, str]]) -> None:
    for name, state in results:
        print(f"{state:15} {name}")
