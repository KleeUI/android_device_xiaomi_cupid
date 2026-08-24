#!/usr/bin/env python3
#
# Copyright (C) 2026 The KleeUI Project
#
# SPDX-License-Identifier: Apache-2.0
#

"""Extract Klee's small Cupid delta inventory from stock firmware or ADB."""

import argparse
from pathlib import Path

from tools.klee_vendor import (
    apply_vendor_patches,
    extract_inventory,
    find_android_root,
    print_results,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=Path, help="Android source root")
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--source",
        type=Path,
        help="directory containing mounted vendor/odm partition trees",
    )
    source.add_argument(
        "--adb", action="store_true", help="extract from the connected Android device"
    )
    parser.add_argument("--adb-bin", default="adb", help="ADB executable")
    parser.add_argument("--serial", help="ADB serial when more than one device exists")
    parser.add_argument(
        "--no-setup",
        action="store_true",
        help="do not normalize generated vendor metadata after extraction",
    )
    args = parser.parse_args()
    if not args.source and not args.adb:
        parser.error("one of --source or --adb is required")

    device_dir = Path(__file__).resolve().parent
    top = args.top.resolve() if args.top else find_android_root(device_dir)
    print_results(
        extract_inventory(
            top,
            device_dir,
            source_root=args.source.resolve() if args.source else None,
            adb=args.adb_bin,
            serial=args.serial,
        )
    )
    if not args.no_setup:
        print_results(apply_vendor_patches(top, device_dir))


if __name__ == "__main__":
    main()
