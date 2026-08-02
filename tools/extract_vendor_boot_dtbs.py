#!/usr/bin/env python3
"""Extract concatenated base DTBs from an Android vendor_boot v3/v4 image."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path


VENDOR_BOOT_MAGIC = b"VNDRBOOT"
FDT_MAGIC = 0xD00DFEED


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def extract(image_path: Path, output_dir: Path) -> None:
    image = image_path.read_bytes()
    if image[:8] != VENDOR_BOOT_MAGIC:
        raise ValueError(f"{image_path} is not an Android vendor_boot image")

    header_version, page_size = struct.unpack_from("<2I", image, 8)
    if header_version not in (3, 4):
        raise ValueError(f"unsupported vendor boot header version {header_version}")

    vendor_ramdisk_size = struct.unpack_from("<I", image, 24)[0]
    header_size = struct.unpack_from("<I", image, 2096)[0]
    dtb_size = struct.unpack_from("<I", image, 2100)[0]
    dtb_offset = align(align(header_size, page_size) + vendor_ramdisk_size, page_size)
    dtb_blob = image[dtb_offset : dtb_offset + dtb_size]
    if len(dtb_blob) != dtb_size:
        raise ValueError("truncated vendor_boot DTB section")

    output_dir.mkdir(parents=True, exist_ok=True)
    offset = 0
    entries: list[tuple[int, int, str]] = []
    while offset < len(dtb_blob):
        if len(dtb_blob) - offset < 8:
            raise ValueError(f"trailing bytes at DTB offset {offset:#x}")
        magic, total_size = struct.unpack_from(">2I", dtb_blob, offset)
        if magic != FDT_MAGIC:
            raise ValueError(f"bad FDT magic at concatenated offset {offset:#x}")
        if total_size < 40 or offset + total_size > len(dtb_blob):
            raise ValueError(f"invalid FDT size {total_size} at offset {offset:#x}")

        payload = dtb_blob[offset : offset + total_size]
        name = f"{len(entries):02d}.dtb"
        (output_dir / name).write_bytes(payload)
        entries.append((offset, total_size, hashlib.sha256(payload).hexdigest()))
        offset += total_size

    if offset != len(dtb_blob):
        raise ValueError("DTB concatenation did not consume the complete section")

    print(f"header_version={header_version}")
    print(f"page_size={page_size}")
    print(f"dtb_offset={dtb_offset}")
    print(f"dtb_size={dtb_size}")
    print(f"dtb_count={len(entries)}")
    for index, (entry_offset, entry_size, digest) in enumerate(entries):
        print(f"{index:02d} offset={entry_offset} size={entry_size} sha256={digest}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    extract(args.image, args.output_dir)


if __name__ == "__main__":
    main()
