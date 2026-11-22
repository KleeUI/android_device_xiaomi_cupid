#!/usr/bin/env python3
#
# Copyright (C) 2026 The KleeUI Project
#
# SPDX-License-Identifier: Apache-2.0
#

"""Prepare merged Cupid vendor inputs or extract the stock Cupid delta."""

import argparse
from pathlib import Path

from tools.klee_vendor import (
    apply_source_patches,
    apply_vendor_patches,
    extract_inventory,
    find_android_root,
    print_results,
)
from tools.klee_vendor_merge import MERGE_RECEIPT, merge_vendor_inputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=Path, help="Android source root")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--prepared-vendor",
        type=Path,
        help="separate Android root containing both prepared Xiaomi vendor trees",
    )
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
        help="skip source patches and legacy vendor normalization",
    )
    args = parser.parse_args()

    device_dir = Path(__file__).resolve().parent
    top = args.top.resolve() if args.top else find_android_root(device_dir)
    if args.prepared_vendor:
        if not args.no_setup:
            apply_source_patches(top, device_dir, check_only=True)
        print_results(merge_vendor_inputs(top, args.prepared_vendor.resolve(), device_dir))
        if not args.no_setup:
            print_results(apply_source_patches(top, device_dir))
        return

    if (top / "vendor/xiaomi/cupid" / MERGE_RECEIPT).exists():
        parser.error("update the delta in the prepared inputs, then rerun --prepared-vendor")
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
