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
patch -p1 < \
    device/xiaomi/cupid/patches/0002-sm8450-common-keep-WfdCommon-off-bootclasspath.patch
```

The patch installs Qualcomm's PowerOffAlarm app on the vendor partition where
its `vendor_poweroffalarm_app` SELinux domain is valid. It changes only the
generated Soong metadata and does not include proprietary APK contents.

The second patch keeps `WfdCommon.jar` installed as a framework package while
removing it from the Android runtime boot class path. This preserves the WFD
package and avoids exposing Qualcomm-private Java packages as platform boot
APIs, which Android 17 rejects during the boot-jar package check.

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
