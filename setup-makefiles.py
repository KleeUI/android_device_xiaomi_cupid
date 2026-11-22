#!/usr/bin/env python3
#
# Copyright (C) 2026 The KleeUI Project
#
# SPDX-License-Identifier: Apache-2.0
#

"""Prepare the Cupid build from merged or legacy vendor inputs."""

import argparse
from pathlib import Path

from tools.klee_vendor import find_android_root, print_results
from tools.klee_vendor_merge import prepare_vendor_tree


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=Path, help="Android source root")
    parser.add_argument(
        "--check", action="store_true", help="report state without changing files"
    )
    args = parser.parse_args()

    device_dir = Path(__file__).resolve().parent
    top = args.top.resolve() if args.top else find_android_root(device_dir)
    print_results(prepare_vendor_tree(top, device_dir, check_only=args.check))


if __name__ == "__main__":
    main()
