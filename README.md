# Xiaomi 12 (cupid) for Klee

This repository is Klee's independently implemented integration for the Xiaomi
12. It targets the Qualcomm SM8450 (`taro`) platform and consumes official
CodeLinaro platform projects through Klee's `qcom/waipio.xml` manifest.

**中文使用与自行编译：** [Xiaomi 12 / Cupid 使用和编译指南](docs/BUILDING.zh-CN.md)
（环境准备、源码同步、专有输入、整包构建、产物检查和故障排查）。

For a scoped record of the most recent documented device check, see the
[R6 post-flash validation report](docs/r6-postflash-validation-20261115.md).

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

Use a full Android source checkout, not a standalone clone of this device
repository. Initialize Cupid with the Waipio manifest:

```bash
repo init -u https://github.com/KleeUI/android.git \
    -b Klee-1.0 -m qcom/waipio.xml
repo sync -c --no-clone-bundle --no-tags -j4
```

The manifest supplies the kernel, device trees, and external module sources,
but it does **not** supply the complete `vendor/xiaomi/cupid` and
`vendor/xiaomi/sm8450-common` proprietary inputs. Prepare those inputs and the
device delta as described above and in the [full guide](docs/BUILDING.zh-CN.md).
Normalize the supported metadata baseline before selecting the product:

```bash
python3 device/xiaomi/cupid/setup-makefiles.py
python3 device/xiaomi/cupid/setup-makefiles.py --check
source build/envsetup.sh
lunch cupid-cp2a-userdebug
klee_build -j8
```

Review the check output: `pending` is not a build-ready state even when the
check exits successfully. `8` is an example job count; select one appropriate
to host memory and CPU capacity. Klee also supports `lunch cupid_userdebug`
when the Klee environment is loaded, with `cp2a` as its default release.

`klee_build` defaults to `droid`; it builds the source kernel and modules
inline. To request packaging artifacts explicitly after preparing the same
environment, use `klee_build -j8 target-files-package otapackage`. The default
output tree is `out/target/product/cupid/`. A successful compile or generated
OTA is not a claim that installation and every hardware function have been
qualified; consult the validation report for the tested scope.

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
