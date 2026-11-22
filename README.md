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

Keep both prepared Xiaomi vendor inputs under a separate Android-shaped
directory. Each input includes its proprietary files and Klee-normalized
build metadata. Use Cupid's extractor to assemble `vendor/xiaomi/cupid` in the
build checkout:

```bash
python3 device/xiaomi/cupid/extract-files.py \
    --prepared-vendor /path/to/prepared-inputs
```

When upgrading an existing build tree, move its `vendor/xiaomi/cupid` and
`vendor/xiaomi/sm8450-common` directories to the prepared input root. Also move
the legacy `device/xiaomi/sm8450-common` directory out of the build checkout
if it contains the standalone `WfdCommon` definition. Cupid now owns that
definition and reads the JAR from its merged proprietary inputs.

The existing `--source` and `--adb` modes extract the Cupid-specific delta.
Use the prepared input root as `--top` and skip setup for a normalized input
tree, then run `--prepared-vendor` again:

```bash
python3 device/xiaomi/cupid/extract-files.py \
    --top /path/to/prepared-inputs --source /path/to/mounted-stock --no-setup
```

Run setup separately to check the merged metadata and apply the source patches:

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

The manifest supplies the kernel, device trees, and external module sources.
Prepare and merge the Xiaomi proprietary inputs as described above and in the
[full guide](docs/BUILDING.zh-CN.md). Check setup before selecting the product:

```bash
python3 device/xiaomi/cupid/setup-makefiles.py
python3 device/xiaomi/cupid/setup-makefiles.py --check
python3 device/xiaomi/cupid/tools/check_source_build_contract.py --top "$PWD"
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

## Source-build contract

`configs/source-build-contract.json` records source module names, their actual
definition files, and product selection requirements. After synchronizing the
complete source tree and normalizing the vendor metadata, check the contract:

```bash
python3 device/xiaomi/cupid/tools/check_source_build_contract.py \
    --top "$PWD"
```

The product parse invokes this same preflight. A missing source definition,
wrong module type, or active same-name vendor prebuilt is an error. AudioReach
uses the Klee Soong adapters, including the matching guards around upstream
Make modules; a directory or a switch alone is not evidence of source ownership.
This static check does not evaluate every build condition or prove compilation.
After generating the build graph, use `--module-info` with the product's current
`module-info.json` to check the selected owners and installed outputs as well.

Display gralloc, mapper, allocator, composer, and `libsdmcore` belong to
`hardware/qcom/display`; the separate display-core tree exports headers and an
optional SnapAlloc implementation. The pinned thermal-engine tree exports
`libThermal_headers` only, not a policy daemon. GNSS private plugins,
CamX/Adreno userspace, firmware, calibration and private audio extensions still
require matching proprietary inputs. Xiaomi-specific kernel drivers missing
from the source tree remain recorded in `configs/source-module-gaps.json`;
this contract does not restore mismatched stock modules or claim complete
hardware support. See [source-build scope](docs/SOURCE_BUILD.zh-CN.md).

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
