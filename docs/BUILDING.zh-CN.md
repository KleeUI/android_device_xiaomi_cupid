# Klee 1.0：Xiaomi 12（Cupid）使用与自行编译

本文面向 `Klee-1.0` 分支，核对日期为 2026-11-15。支持对象是 Xiaomi 12，
代号 `cupid`、平台 SM8450 / `taro`。下列编译命令在 Linux 的 Bash 中执行；
除特别说明外，工作目录始终是完整 Android 源码根目录。

## 1. 项目组成与当前边界

本仓库是设备集成层，不是独立可编译的完整 ROM。完整工作区由 Repo 管理：

| 路径 | 用途 |
| --- | --- |
| `.repo/manifests` | `KleeUI/android` 的平台与设备清单 |
| `build/` | Android 构建环境和打包工具 |
| `vendor/klee/` | Klee 产品配置、构建包装函数、内核构建工具 |
| `device/xiaomi/cupid/` | 本设备的产品、分区、DTS、模块加载和 SELinux 配置 |
| `kernel_platform/` | 清单指定的 Waipio GKI 内核源码及工具 |
| `vendor/qcom/opensource/` | Qualcomm HAL 与外部内核模块源码 |
| `vendor/xiaomi/cupid/`、`vendor/xiaomi/sm8450-common/` | 需另行准备的完整专有输入 |

**公开清单加本仓库的提取脚本，目前不足以从零重建两份完整专有输入。**
`proprietary-files.txt` 仅记录 Cupid 设备差量；没有完整 vendor 输入时，应先补齐，
不能通过删除缺失依赖、混入另一 ROM 的模块或复制旧 `out/` 来绕过。

当前配置是开发用途：`BoardConfig.mk` 使用 AVB 测试密钥，root vbmeta 参数为
`--flags 3`。这不是可直接锁定 bootloader 的正式安全发行配置。
已有的 [R6 刷机验证记录](r6-postflash-validation-20261115.md) 只覆盖其列明的
镜像回读、启动和部分硬件检查，不代表所有硬件、OTA 安装或长期稳定性都已验收。

## 2. 准备 Linux 构建机

- 使用 64 位 x86 Linux 和区分大小写的本地文件系统，建议 Ubuntu 22.04 LTS。
  Windows 可作为终端或 ADB 主机；本文未验证在 Windows 原生文件系统上构建。
- 按 [AOSP 环境要求](https://source.android.com/docs/setup/start/requirements)
  准备至少 64 GB 内存及 400 GB 可用磁盘空间。Klee 还包括 Qualcomm 内核、模块、
  专有输入和打包产物，建议为工作区预留约 1 TB，并在构建前检查实际剩余空间。
  后一个数值是容量规划建议，不是本项目测得的固定最低门槛。
- 保持 GitHub、android.googlesource.com 和 git.codelinaro.org 网络可达。
  构建工具链由同步后的源码树提供，不需要先安装任意版本的外部 Android Clang。

Ubuntu 22.04 的依赖安装示例（AOSP 基础包加本项目内核常用工具）：

```bash
sudo apt-get update
sudo apt-get install \
  git-core gnupg flex bison build-essential zip curl zlib1g-dev \
  libc6-dev-i386 x11proto-core-dev libx11-dev lib32z1-dev libgl1-mesa-dev \
  libxml2-utils xsltproc unzip fontconfig \
  python3 repo bc bzip2 cpio file patch rsync kmod libssl-dev libelf-dev \
  libncurses-dev lz4 zstd device-tree-compiler

git --version
python3 --version
repo version
df -h .
df -i .
free -h
```

若发行版不提供 `repo` 包，按
[AOSP Repo 安装说明](https://source.android.com/docs/setup/start/requirements#install-repo)
安装启动器，再继续。Git 的作者姓名和邮箱请设置为你自己的身份。

## 3. 初始化并同步正确的清单

首次使用建议新建工作目录，不在本地日志、镜像或实验目录上直接初始化：

```bash
mkdir -p "$HOME/android/klee"
cd "$HOME/android/klee"
repo init -u https://github.com/KleeUI/android.git \
  -b Klee-1.0 -m qcom/waipio.xml
repo sync -c --no-clone-bundle --no-tags -j4
```

`Klee-1.0` 是分支名，大小写按上述命令填写；仓库名是 `KleeUI/android`。
`qcom/waipio.xml` 会包含 QSSI 和基础清单，并同步 Cupid 设备树、Waipio 内核和
配套模块。只初始化默认清单不会得到完整的 Cupid 构建输入。

`-j4` 是下载并行数，与后面的编译并行数不同。遇到下载失败先修复网络并重新同步；
默认不使用 `--force-checkout`，以免覆盖你在各子仓库中的修改。

同步后进行路径检查：

```bash
test -f build/envsetup.sh
test -f vendor/klee/vendorsetup.sh
test -f device/xiaomi/cupid/AndroidProducts.mk
test -f kernel_platform/msm-kernel/Makefile
test -f kernel_platform/common/build.config.msm.waipio
test -f kernel_platform/msm-kernel/arch/arm64/boot/dts/vendor/Makefile
python3 .repo/manifests/tools/check_manifest_sources.py
repo status
```

以上文件检查中任何一项失败都应先处理。清单会创建 `kernel_platform/common`
和内核 vendor DTS 等链接；不要另行克隆随机内核，也不要用库存 DTB/DTBO 替换链接。
source-policy 校验只检查清单来源与固定版本策略，不会验证每个项目的下载完整性或硬件功能。

## 4. 准备完整专有输入和设备差量

先从你有权使用、且与当前设备集成匹配的来源准备以下目录及其全部依赖文件：

```text
vendor/xiaomi/cupid/Android.bp
vendor/xiaomi/cupid/cupid-vendor.mk
vendor/xiaomi/cupid/proprietary/...
vendor/xiaomi/sm8450-common/Android.bp
vendor/xiaomi/sm8450-common/sm8450-common-vendor.mk
vendor/xiaomi/sm8450-common/proprietary/...
```

这两份完整 vendor tree 不在当前 Waipio 清单中；清单中的
`vendor/xiaomi/sm8450-qcril` 也不能代替它们。当前仓库没有可据此编写的完整公开
生成命令，因此这里不提供未经核实的 blob 仓库地址。请保留输入来源、版本、文件摘要
和许可证记录；只有上述几个元数据文件存在，也不等于所有专有文件都已齐全。

完整输入准备好后，再提取设备差量。以下两种方式任选一种。

### 从解包或挂载后的固件目录提取

将下面示例路径替换为实际目录。其下应有 `vendor/etc/...`、`vendor/bin/...` 等
分区相对路径，而不是直接传入 OTA ZIP 或原始 `.img`：

```bash
python3 device/xiaomi/cupid/extract-files.py \
  --source /path/to/mounted-stock
```

### 从能访问对应文件的匹配设备提取

```bash
adb devices
python3 device/xiaomi/cupid/extract-files.py --adb
```

多台设备连接时，给提取命令增加 `--serial` 并指定实际 ADB 序列号。
脚本使用 `adb pull`；若设备不允许读取某文件，需先解决访问权限或使用固件目录方式。
不要从缺少匹配文件的测试系统中补齐库存专有输入。

`proprietary-files.txt` 当前注明未单独固定摘要的差量基线为
`OS3.0.4.0.VLCMIXM`。另一个 `OS3.0.3.0.VLCCNXM` DTB 摘要文件仅作外部对照，
两者用途不同，不应当作可随意混搭固件的依据。

### 规范化元数据

提取器默认会调用同一套规范化逻辑；已有差量文件时也可单独执行：

```bash
python3 device/xiaomi/cupid/setup-makefiles.py
python3 device/xiaomi/cupid/setup-makefiles.py --check
```

补丁涉及两份 vendor 元数据及配套 location 源码元数据，因此必须在完整源码同步后运行。
请检查输出状态：正常应用后再次检查应显示 `already-applied`；`pending` 表示尚未应用。
`--check` 只报告状态，出现 `pending` 时也可能返回退出码 0，不能只看退出码判断就绪。
若提示 `ambiguous or has drift`，先比较受影响文件和补丁基线；不要强制套补丁或删除检查。
在同步或重置被补丁修改的子仓库前，先记录并保存这些本地修改。

## 5. 选择目标并编译

以下命令继续在完整源码根目录执行：

```bash
source build/envsetup.sh
lunch cupid-cp2a-userdebug
type klee_build
printf 'product=%s release=%s variant=%s\n' \
  "$TARGET_PRODUCT" "$TARGET_RELEASE" "$TARGET_BUILD_VARIANT"
```

产品应为 `cupid`、release 为 `cp2a`、variant 为 `userdebug`。
Klee 环境也支持 `lunch cupid_userdebug` 简写，默认 release 为 `cp2a`。
设备还登记了 `cupid-cp2a-user`、`cupid-cp2a-eng`；首次复现建议使用 `userdebug`。

当前设备和清理规则有默认 `out/` 路径约定。本文统一使用默认输出目录，
不建议在首次复现时自行更改 `OUT_DIR`。在同一源码和输出树上一次只运行一个构建。

### 整包编译

```bash
mkdir -p build-records
repo manifest -r -o build-records/manifest.xml
repo status > build-records/repo-status.txt
set -o pipefail
klee_build -j8 2>&1 | tee build-records/build.log
```

`8` 是示例并行数，可按 CPU 和内存调整为正整数。`klee_build` 不指定目标时构建
`droid`，并把所选并行数用于源码内核构建；`mka bacon -j8` 也只是完整 `droid`
构建的入口，并不额外完成正式签名或设备功能验收。
构建失败以命令退出状态和日志中的首个实际错误为准，不能只看最后是否出现镜像文件。

首次成功后，需要 target-files 和 OTA 时，显式构建：

```bash
set -o pipefail
klee_build -j8 target-files-package otapackage \
  2>&1 | tee build-records/package.log
```

内核、DTB、DTBO 和外部模块由同一构建图统一生成，无需先手工编译或替换库存内核。
仅调试内核 bundle 时，在同样的输入和环境准备完成后可执行：

```bash
klee_build -j8 klee-kernel
```

这个目标只生成内核相关产物，不代表 Android 镜像和整包已重新打包。

## 6. 识别、检查和保留产物

默认产品输出为 `out/target/product/cupid/`。按实际执行的目标检查：

| 产物 | 用途 |
| --- | --- |
| `boot.img`、`vendor_boot.img`、`dtbo.img`、`recovery.img` | 启动、模块/ramdisk、设备树与恢复镜像 |
| `system.img`、`system_ext.img`、`product.img`、`vendor.img`、`odm.img`、`vendor_dlkm.img` | Android 分区镜像 |
| `vbmeta.img`、`vbmeta_system.img` | 本次镜像对应的 AVB 元数据 |
| `obj/KLEE_KERNEL_DIST/` | 源码内核 `Image`、`dtb.img`、`dtbo.img`、`modules/` 等中间交付物 |
| `obj/PACKAGING/target_files_intermediates/*.zip` | target-files；供重新签名、生成 OTA 和审计使用 |
| `*ota*.zip` | `otapackage` 目标的输出；准确文件名以本次日志为准 |

```bash
find out/target/product/cupid -maxdepth 5 -type f \
  \( -name '*target_files*.zip' -o -name '*ota*.zip' \) -print

sha256sum out/target/product/cupid/{boot,vendor_boot,dtbo,recovery,system,system_ext,product,vendor,odm,vendor_dlkm,vbmeta,vbmeta_system}.img \
  > build-records/images.sha256
```

缺少预期镜像或打包报错时不要拼入以前构建的同名文件。保留本次成功构建的
`manifest.xml`、本地补丁、专有输入版本、完整日志和摘要；`repo manifest -r`
不会记录未提交补丁，也不会自动记录清单外的 vendor 输入，需要另行归档。

当前分区配置使用 ext4 的 system/system_ext/product、EROFS 的 vendor，以及
源码构建的 vendor_dlkm；改变文件系统、AVB、分区大小或内核 ABI 后必须重新检查整个
配套产物，不能只因为一个分区能构建就认为整包可安装。

## 7. 更新源码、增量编译与干净重建

先执行 `repo status` 并保存自己的提交、补丁和专有输入，再同步。规范化步骤可能修改
多个子仓库，不能把这些差异全部当作无用文件丢弃。更新完成后重新检查专有输入基线，
运行规范化检查，再 `source`、`lunch`、`klee_build`。

普通源码调整可在同一正确基线上增量构建。若需明确的干净重建，先确认没有其他构建
进程，并已保存需要的产物和日志，再在已选定产品的构建环境中执行：

```bash
klee_build clobber
klee_build -j8
```

`clobber` 会删除构建输出，随后需要完整重编；它不会替你补齐专有输入或保存未提交修改。
不要将清理输出替换为删除源码树、`.repo` 或固件备份。

## 8. 如何使用构建结果和验证设备

生成的 target-files 是打包输入，不是可以直接刷入分区的镜像。OTA 的安装需要与
设备 recovery、分区布局、当前基线和密钥匹配；本指南不把“生成 ZIP”视为“已验证可刷”。
R6 使用的是有独立回读验证的限定分区测试流程，不是通用首次安装教程。
首次安装应使用针对 Cupid、与该次产物配套且已验证的安装说明；当前公开文档尚未提供
经过从零实测的通用安装流程。

已安装匹配测试系统后，可通过设置开启开发者选项和 USB 调试，并在手机上授权主机。
以下命令只读取状态（ADB 处于 `device` 状态时使用）：

```bash
adb devices
adb shell getprop ro.product.device
adb shell getprop ro.boot.slot_suffix
adb shell getprop sys.boot_completed
adb shell getprop sys.system_server.start_count
adb shell getenforce

mkdir -p device-logs
adb logcat -b all -d -v threadtime > device-logs/logcat.txt
adb shell dumpsys dropbox --print system_server_crash \
  > device-logs/system-server-crash.txt
```

正常启动检查应结合 `cupid` 身份、实际槽位、`boot_completed=1`、SELinux 状态和
同一启动内的重启/崩溃记录。Wi-Fi 扫描不等于联网、蓝牙发现不等于配对、NFC 服务开启
不等于读卡；相机预览也不能替代拍照、录像和长期运行测试。测试相机后退出相机应用。
日志可能含序列号、网络标识和用户数据，公开前先脱敏。

## 9. 常见问题

| 现象 | 首先检查 |
| --- | --- |
| 找不到 `cupid` 产品或 `vendor/klee` | 是否使用 `-m qcom/waipio.xml`，是否完整同步并在源码根目录执行 |
| `klee_build: command not found` | 重新 `source build/envsetup.sh`，检查 `vendor/klee/vendorsetup.sh` 是否存在且已加载 |
| `vendor input is incomplete` / 缺失专有文件 | 两份完整 vendor 输入及设备差量；仅同步 QCRIL 仓库不够 |
| 规范化显示 `pending` 或 `drift` | 查看完整输出和补丁基线；`--check` 不负责应用，也不保证 pending 返回非零 |
| 缺少 source DT / KMI / `.ko` 或 vermagic 不匹配 | 清单链接、源码版本、内核和模块是否同次生成；不要用旧模块或库存 DTBO 补位 |
| `llvm-nm` / `depmod` / `fdtoverlay` 缺失 | 工具链同步情况，以及主机 kmod、device-tree-compiler 等依赖 |
| `No space left on device` | `df -h`、`df -i`；先归档需要的产物，停止其他构建后再清理输出 |
| 进程被 `Killed` 或内存不足 | 检查内存/内核日志，降低 `-j`；必要时在构建 shell 设置 `KLEE_SOONG_INCREMENTAL_ANALYSIS=false` |
| 镜像超出分区容量或打包失败 | 核对当前 `BoardConfig.mk` 和本次产物；不要截断文件或擅自扩大设备分区 |

本文命令已按公开源码入口和脚本参数核对；本次文档更新没有重新执行完整下载、
从零编译或首次刷机，因此不作这些流程已端到端复现通过的声明。
