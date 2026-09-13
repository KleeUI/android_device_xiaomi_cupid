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

## Device-tree source policy

Klee builds the Cupid DTB and DTBO images from source. `BoardConfig.mk`
deliberately rejects `BOARD_PREBUILT_DTBIMAGE_DIR` and
`BOARD_PREBUILT_DTBOIMAGE`; a missing source tree is a configuration error, not
permission to fall back to an extracted Xiaomi image.

The source corpus must come from pinned MiCode or CodeLinaro revisions with
their original notices and an auditable commit or tree identifier. Klee owns
the build adapter, variant selection, output normalization, selector ordering,
overlay composition, and semantic validation described by
`configs/kernel-dt-layout.json`. LineageOS may be used as a differential
reference while investigating hardware coverage, but it is not an accepted
source import or build dependency.

Stock firmware remains useful as an external test oracle. The extraction tool
may be used to unpack a matching `vendor_boot.img` into a scratch directory for
comparison:

```bash
python3 device/xiaomi/cupid/tools/extract_vendor_boot_dtbs.py \
    vendor_boot.img \
    /tmp/cupid-stock-dtb
```

`configs/vendor_boot_dtbs_os3.0.3.0.sha256` records the ordered Cupid OS
3.0.3.0.VLCCNXM baseline. It is validation data only and is never consumed as a
build input.
