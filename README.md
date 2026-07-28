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

The device-specific Make, Soong, partition, product, and overlay configuration
in this repository is authored for Klee. Common Qualcomm implementation comes
from pinned CodeLinaro projects and retains its upstream history and licenses.
Xiaomi and Qualcomm proprietary components belong in `vendor/xiaomi/cupid` and
are not committed here.

## Proprietary metadata fixes

After populating `vendor/xiaomi`, apply the device-maintained metadata fixes
before building:

```bash
patch -p1 < \
    device/xiaomi/cupid/patches/0001-sm8450-common-install-PowerOffAlarm-on-vendor.patch
```

The patch installs Qualcomm's PowerOffAlarm app on the vendor partition where
its `vendor_poweroffalarm_app` SELinux domain is valid. It changes only the
generated Soong metadata and does not include proprietary APK contents.

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
flashable image, extract the concatenated DTB from `vendor_boot` and the DTBO
from the active slot of a matching `cupid` device, then place them at:

```text
vendor/xiaomi/cupid/proprietary/dtb/cupid-stock.dtb
vendor/xiaomi/cupid/proprietary/dtbo.img
```

These hardware-specific images are local proprietary inputs and must not be
committed to the public device repository.
