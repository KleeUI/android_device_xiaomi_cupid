# Xiaomi 12 (cupid) for Klee

This repository is Klee's independently implemented integration for the Xiaomi
12. It targets the Qualcomm SM8450 (`taro`) platform and consumes official
CodeLinaro platform projects through Klee's `qcom/waipio.xml` manifest.

## Hardware baseline

- SoC: Qualcomm SM8450
- Device board: `taro`
- Launch API: 32
- Kernel ABI: GKI 5.10, arm64, 4 KiB pages
- Boot image: header v4, 192 MiB
- Vendor boot image: header v4, 96 MiB
- DTBO image: 24 MiB
- Super partition: 9,126,805,504 bytes
- Storage: Virtual A/B dynamic partitions
- Display: 1080 × 2400 at 440 dpi, up to 120 Hz

## Source boundaries

The device-specific Make, Soong, partition, product, overlay, and vendor
normalization code in this repository is authored for Klee. Common Qualcomm
implementation comes from pinned CodeLinaro projects and retains its upstream
history and licenses. Xiaomi and Qualcomm proprietary binaries belong below
`vendor/xiaomi` and are not committed here.

The scripts in this repository do not contain or import LineageOS extraction
code. They copy Klee's small device-delta inventory from a user-owned stock
image and apply reviewable metadata patches to an already populated vendor
tree. The current `proprietary-files.txt` is not a complete inventory for the
two large vendor repositories; a clean-room regeneration of those repositories
also requires their complete, independently audited stock inventories.

## Proprietary input workflow

First populate `vendor/xiaomi/cupid` and `vendor/xiaomi/sm8450-common` from an
authorized source. To copy Klee's Cupid delta from mounted stock partitions and
normalize the generated metadata in one command, run:

```bash
python3 device/xiaomi/cupid/extract-files.py \
    --source /path/to/mounted-stock
```

The source directory must contain partition-relative paths such as
`vendor/etc/acdbdata/...`. A rooted, matching Cupid can be used instead:

```bash
python3 device/xiaomi/cupid/extract-files.py --adb
```

Metadata normalization can be run independently and is idempotent:

```bash
python3 device/xiaomi/cupid/setup-makefiles.py
python3 device/xiaomi/cupid/setup-makefiles.py --check
```

Each patch is accepted in exactly one of two states: cleanly applicable or
already applied. A partially applied patch or a changed generated baseline is
reported as an error and is never guessed through.

`klee-compat.mk` is versioned in this device repository. The generated vendor
tree supplies the proprietary module definitions, while the device repository
owns the Klee product-package selection.

## Build

Initialize Klee with the Waipio manifest, provide the kernel and proprietary
repositories, then run:

```bash
source build/envsetup.sh
lunch cupid_userdebug
klee_build -jXX
```

## Stock DTB and DTBO

The public CodeLinaro Waipio 5.10 release does not include the board
device-tree source used by retail Xiaomi 12 firmware. Before building a
flashable image, extract the complete, ordered base-DTB table from
`vendor_boot` and the DTBO from the active slot of a matching `cupid` device.
Do not filter the base table down to generic Waipio DTBs: the retail Cupid
overlays reference Xiaomi downstream display, camera, and audio nodes that are
absent from those public base trees.

Populate and verify the local DTB directory with:

```bash
python3 device/xiaomi/cupid/tools/extract_vendor_boot_dtbs.py \
    vendor_boot.img \
    vendor/xiaomi/cupid/proprietary/kernel/dtb

cd vendor/xiaomi/cupid/proprietary/kernel/dtb
sha256sum -c \
    ../../../../../../device/xiaomi/cupid/configs/vendor_boot_dtbs_os3.0.3.0.sha256
```

Place the matching DTBO at:

```text
vendor/xiaomi/cupid/proprietary/dtbo.img
```

The checked hash manifest describes Cupid OS 3.0.3.0.VLCCNXM. These
hardware-specific images remain local proprietary inputs and are not committed
to the public device repository.
