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
import shutil
import subprocess
import tempfile
from typing import Iterable


PATCH_NAMES = (
    "0001-sm8450-common-adapt-generated-metadata-for-klee.patch",
    "0002-sm8450-common-keep-WfdCommon-off-bootclasspath.patch",
    "0003-cupid-drop-lineage-soong-imports.patch",
    "0004-cupid-install-klee-stock-delta-files.patch",
)

REQUIRED_VENDOR_FILES = (
    "vendor/xiaomi/cupid/Android.bp",
    "vendor/xiaomi/cupid/cupid-vendor.mk",
    "vendor/xiaomi/sm8450-common/Android.bp",
    "vendor/xiaomi/sm8450-common/sm8450-common-vendor.mk",
)


class VendorPreparationError(RuntimeError):
    """Raised when the local vendor inputs cannot be normalized safely."""


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


def _patch_probe(top: Path, patch_file: Path, reverse: bool) -> bool:
    command = [
        "patch",
        "-p1",
        "--dry-run",
        "--batch",
        "--silent",
        "--reverse" if reverse else "--forward",
        f"--input={patch_file}",
    ]
    return _run(command, top).returncode == 0


def apply_vendor_patches(
    top: Path, device_dir: Path, *, check_only: bool = False
) -> list[tuple[str, str]]:
    """Apply Klee metadata patches once, or verify their current state.

    A patch is either forward-applicable (pending) or reverse-applicable
    (already applied).  Any third state is treated as drift and is never
    modified automatically.
    """
    missing = [path for path in REQUIRED_VENDOR_FILES if not (top / path).is_file()]
    if missing:
        raise VendorPreparationError(
            "vendor input is incomplete:\n  " + "\n  ".join(missing)
        )

    results: list[tuple[str, str]] = []
    for name in PATCH_NAMES:
        patch_file = device_dir / "patches" / name
        if not patch_file.is_file():
            raise VendorPreparationError(f"missing metadata patch: {patch_file}")

        if _patch_probe(top, patch_file, reverse=False):
            state = "pending"
            if not check_only:
                command = [
                    "patch",
                    "-p1",
                    "--batch",
                    "--forward",
                    f"--input={patch_file}",
                ]
                result = _run(command, top)
                if result.returncode:
                    raise VendorPreparationError(
                        f"failed to apply {name}:\n{result.stdout.rstrip()}"
                    )
                state = "applied"
        elif _patch_probe(top, patch_file, reverse=True):
            state = "already-applied"
        else:
            raise VendorPreparationError(
                f"{name} matches neither the generated nor normalized tree; "
                "regenerate vendor metadata or review the drift manually"
            )
        results.append((name, state))
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
