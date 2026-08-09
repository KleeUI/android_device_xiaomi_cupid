#
# Copyright (C) 2026 The KleeUI Project
#
# SPDX-License-Identifier: Apache-2.0
#

DEVICE_PATH := device/xiaomi/cupid

TARGET_BOARD_PLATFORM := taro
TARGET_BOOTLOADER_BOARD_NAME := taro
TARGET_SCREEN_DENSITY := 440
TARGET_VENDOR_PROP := $(DEVICE_PATH)/configs/vendor.prop

# Register Waipio/Taro with the shared Qualcomm build helpers. Without this,
# legacy SDK-only tasks treat cupid as a non-Qualcomm target and re-enter AOSP
# configuration after product variables have become read-only.
QCOM_BOARD_PLATFORMS += taro

TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-a-branchprot
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_VARIANT := kryo

TARGET_2ND_ARCH := arm
TARGET_2ND_ARCH_VARIANT := armv8-2a
TARGET_2ND_CPU_ABI := armeabi-v7a
TARGET_2ND_CPU_ABI2 := armeabi
TARGET_2ND_CPU_VARIANT := cortex-a75

TARGET_NO_BOOTLOADER := true
TARGET_NO_KERNEL := false
TARGET_USES_UEFI := true
TARGET_HAS_GENERIC_KERNEL_HEADERS := true
TARGET_BOARD_KERNEL_HEADERS := $(DEVICE_PATH)/kernel-headers

BOARD_VNDK_VERSION := current
BOARD_PROPERTY_OVERRIDES_SPLIT_ENABLED := true

BOARD_USES_METADATA_PARTITION := true
BOARD_USES_RECOVERY_AS_BOOT := false
TARGET_NO_RECOVERY := false
BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true
AB_OTA_UPDATER := true

BOARD_BOOT_HEADER_VERSION := 4
BOARD_MKBOOTIMG_ARGS := --header_version $(BOARD_BOOT_HEADER_VERSION)
BOARD_KERNEL_PAGESIZE := 4096
# Xiaomi's SM8450 ABL loads the v4 boot components from the zero-based
# addresses encoded by the stock Cupid images.  The Android default base of
# 0x10000000 shifts the kernel, ramdisk, tags, and DTB addresses out of the
# layout expected by this boot chain.
BOARD_KERNEL_BASE := 0x00000000
BOARD_RAMDISK_USE_LZ4 := true
BOARD_INCLUDE_DTB_IN_BOOTIMG := true
BOARD_INCLUDE_RECOVERY_DTBO := true
BOARD_VENDOR_RAMDISK_FRAGMENTS += dlkm
BOARD_VENDOR_RAMDISK_FRAGMENT.dlkm.KERNEL_MODULE_DIRS := top

BOARD_KERNEL_CMDLINE := \
    disable_dma32=on \
    log_buf_len=2M \
    mtdoops.dump_oops=0 \
    mtdoops.fingerprint=Klee-1.0 \
    mtdoops.mtddev=0 \
    mtdoops.record_size=2097152 \
    printk.always_kmsg_dump=1

BOARD_BOOTCONFIG := \
    androidboot.hardware=qcom \
    androidboot.product.vendor.sku=taro \
    androidboot.memcg=1 \
    androidboot.klee_firststage_diag=true \
    androidboot.usbcontroller=a600000.dwc3

TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/recovery.fstab
TARGET_RECOVERY_PIXEL_FORMAT := RGBX_8888

# Partition geometry measured from a retail Xiaomi 12.
BOARD_BOOTIMAGE_PARTITION_SIZE := 201326592
BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE := 100663296
BOARD_DTBOIMG_PARTITION_SIZE := 25165824
BOARD_RECOVERYIMAGE_PARTITION_SIZE := 104857600
BOARD_FLASH_BLOCK_SIZE := 131072

BOARD_SUPER_PARTITION_SIZE := 9126805504
BOARD_SUPER_PARTITION_GROUPS := klee_dynamic_partitions
BOARD_KLEE_DYNAMIC_PARTITIONS_SIZE := 9122611200
BOARD_KLEE_DYNAMIC_PARTITIONS_PARTITION_LIST := \
    system \
    system_ext \
    product \
    vendor \
    odm \
    vendor_dlkm

BOARD_SYSTEMIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_SYSTEM_EXTIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_PRODUCTIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_ODMIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_VENDOR_DLKMIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_USERDATAIMAGE_FILE_SYSTEM_TYPE := f2fs
TARGET_USERIMAGES_USE_EXT4 := true
TARGET_USERIMAGES_USE_F2FS := true
BOARD_EXT4_SHARE_DUP_BLOCKS := true

TARGET_COPY_OUT_VENDOR := vendor
TARGET_COPY_OUT_ODM := odm
TARGET_COPY_OUT_VENDOR_DLKM := vendor_dlkm
TARGET_COPY_OUT_PRODUCT := product
TARGET_COPY_OUT_SYSTEM_EXT := system_ext
BOARD_USES_VENDOR_DLKMIMAGE := true

BOARD_AVB_ENABLE := true
BOARD_AVB_ALGORITHM := SHA256_RSA2048
BOARD_AVB_KEY_PATH := external/avb/test/data/testkey_rsa2048.pem
BOARD_AVB_MAKE_VBMETA_IMAGE_ARGS += --flags 3
BOARD_AVB_RECOVERY_KEY_PATH := external/avb/test/data/testkey_rsa2048.pem
BOARD_AVB_RECOVERY_ALGORITHM := SHA256_RSA2048
BOARD_AVB_RECOVERY_ROLLBACK_INDEX := 1
BOARD_AVB_RECOVERY_ROLLBACK_INDEX_LOCATION := 1
BOARD_AVB_VBMETA_SYSTEM := system system_ext product
BOARD_AVB_VBMETA_SYSTEM_KEY_PATH := external/avb/test/data/testkey_rsa2048.pem
BOARD_AVB_VBMETA_SYSTEM_ALGORITHM := SHA256_RSA2048
BOARD_AVB_VBMETA_SYSTEM_ROLLBACK_INDEX := $(PLATFORM_SECURITY_PATCH_TIMESTAMP)
BOARD_AVB_VBMETA_SYSTEM_ROLLBACK_INDEX_LOCATION := 2
BOARD_MOVE_GSI_AVB_KEYS_TO_VENDOR_BOOT := true

AB_OTA_PARTITIONS := \
    boot \
    dtbo \
    odm \
    product \
    recovery \
    system \
    system_ext \
    vbmeta \
    vbmeta_system \
    vendor \
    vendor_boot \
    vendor_dlkm

# Qualcomm platform capabilities used by the pinned CodeLinaro HALs.
TARGET_USES_ION := true
TARGET_USES_NEW_ION := true
TARGET_USES_NEW_ION_API := true
USE_SENSOR_MULTI_HAL := true
TARGET_USES_QCOM_BSP := true
TARGET_ENABLE_QC_AV_ENHANCEMENTS := true

# Build the fence and external-display providers consumed by the source-built
# display DLKM. The public Waipio kernel kit exports their ABI but does not
# contain their implementations.
TARGET_QCOM_MSM_EXT_DISPLAY_DLKM := true
TARGET_QCOM_SYNC_FENCE_DLKM := true
TARGET_QCOM_HW_FENCE_DLKM := true
TARGET_QCOM_SYNX_DLKM := false
CONFIG_MSM_MMRM := y

TARGET_KERNEL_VERSION := 5.10

TARGET_USES_QCOM_LEGACY_QMI_LOCATION := false
TARGET_BUILD_QCOM_SIGMA_DUT := false

# Use the modern UFS BSG UAPI exposed by the GKI headers. Without this,
# Qualcomm's recovery extension falls back to removed legacy UFS ioctls.
SOONG_CONFIG_NAMESPACES += ufsbsg
SOONG_CONFIG_ufsbsg += ufsframework
SOONG_CONFIG_ufsbsg_ufsframework := bsg

# AOSP 17 names these prebuilt policy inputs explicitly. Keep the upstream
# CodeLinaro policy content while avoiding its obsolete BoardConfig aliases.
BOARD_SYSTEM_EXT_SEPOLICY_PREBUILT_DIRS += \
    device/qcom/sepolicy/generic
BOARD_PRODUCT_SEPOLICY_PREBUILT_DIRS += \
    device/qcom/sepolicy/generic/product

SYSTEM_EXT_PUBLIC_SEPOLICY_DIRS += \
    device/qcom/sepolicy/generic/public \
    device/qcom/sepolicy/generic/public/attribute
SYSTEM_EXT_PRIVATE_SEPOLICY_DIRS += \
    device/qcom/sepolicy/generic/private
PRODUCT_PUBLIC_SEPOLICY_DIRS += \
    device/qcom/sepolicy/generic/product/public
PRODUCT_PRIVATE_SEPOLICY_DIRS += \
    device/qcom/sepolicy/generic/product/private

BOARD_VENDOR_SEPOLICY_DIRS += $(wildcard \
    $(DEVICE_PATH)/sepolicy/vendor \
    device/qcom/sepolicy_vndr \
    device/qcom/sepolicy_vndr/generic/vendor/common \
    device/qcom/sepolicy_vndr/generic/vendor/common/attribute \
    device/qcom/sepolicy_vndr/generic/vendor/taro \
    device/qcom/sepolicy_vndr/qva/vendor/common \
    device/qcom/sepolicy_vndr/qva/vendor/taro)

# Klee inline GKI.
BOARD_USES_GENERIC_KERNEL_IMAGE := true
TARGET_KERNEL_ARCH := arm64
BOARD_KERNEL_IMAGE_NAME := Image
TARGET_KERNEL_SOURCE := kernel/xiaomi/sm8450
TARGET_KERNEL_CONFIG := \
    gki_defconfig \
    vendor/waipio_GKI.config \
    vendor/xiaomi_GKI.config \
    vendor/cupid_GKI.config \
    vendor/debugfs.config
TARGET_KERNEL_CONFIG_EXT += \
    $(DEVICE_PATH)/configs/klee_GKI.config
TARGET_KERNEL_ADDITIONAL_FLAGS := TARGET_PRODUCT=$(PRODUCT_DEVICE)
TARGET_KERNEL_EXT_MODULE_ROOT := kernel/xiaomi/sm8450-modules
TARGET_KERNEL_EXT_MODULES := \
    qcom/opensource/mmrm-driver \
    qcom/opensource/audio-kernel \
    qcom/opensource/camera-kernel \
    qcom/opensource/cvp-kernel \
    qcom/opensource/dataipa/drivers/platform/msm \
    qcom/opensource/datarmnet/core \
    qcom/opensource/datarmnet-ext/aps \
    qcom/opensource/datarmnet-ext/offload \
    qcom/opensource/datarmnet-ext/shs \
    qcom/opensource/datarmnet-ext/perf \
    qcom/opensource/datarmnet-ext/perf_tether \
    qcom/opensource/datarmnet-ext/sch \
    qcom/opensource/datarmnet-ext/wlan \
    qcom/opensource/display-drivers/msm \
    qcom/opensource/eva-kernel \
    qcom/opensource/video-driver \
    qcom/opensource/wlan/qcacld-3.0/.qca6490 \
    qcom/opensource/wlan/qcacld-3.0/.qca6750
TARGET_NEEDS_DTBOIMAGE := true

# The Waipio GKI keeps storage, clocks, regulators, interrupt routing and
# IOMMU support modular. These modules must be available before first-stage
# init can discover UFS and mount the dynamic partitions. Android 17's
# filesystem generator consumes source files while it creates its graph, so
# the matching module kit is retained in the device's private vendor input.
CUPID_KERNEL_PREBUILT_DIR := vendor/xiaomi/cupid/proprietary/kernel
CUPID_KERNEL_MODULE_DIR := $(CUPID_KERNEL_PREBUILT_DIR)/modules

# Qualcomm Android.mk files are scanned even though Cupid packages the Klee
# source build directly.  Point their parse-time KERNEL_KIT probe at the same
# ABI-verified two-stage kit so unrequested legacy DLKM rules remain dormant.
KERNEL_PREBUILT_DIR := $(CUPID_KERNEL_PREBUILT_DIR)
CUPID_FIRST_STAGE_MODULES_FILE := \
    $(TARGET_KERNEL_SOURCE)/modules.list.msm.waipio
CUPID_SECOND_STAGE_MODULES_FILE := \
    $(DEVICE_PATH)/configs/modules.list.second_stage
CUPID_VENDOR_DLKM_EXCLUSIVE_MODULES_FILE := \
    $(DEVICE_PATH)/configs/modules.list.vendor_dlkm
ifeq ($(wildcard $(CUPID_FIRST_STAGE_MODULES_FILE)),)
$(error Missing first-stage kernel module list: $(CUPID_FIRST_STAGE_MODULES_FILE))
endif
ifeq ($(wildcard $(CUPID_SECOND_STAGE_MODULES_FILE)),)
$(error Missing second-stage kernel module list: $(CUPID_SECOND_STAGE_MODULES_FILE))
endif
ifeq ($(wildcard $(CUPID_VENDOR_DLKM_EXCLUSIVE_MODULES_FILE)),)
$(error Missing vendor_dlkm kernel module list: $(CUPID_VENDOR_DLKM_EXCLUSIVE_MODULES_FILE))
endif
# Preserve Qualcomm's dependency order while removing repeated entries.  The
# public Waipio list names both watchdog modules twice; loading an already
# loaded first-stage module is unnecessary and can make early-init diagnostics
# look like a real module failure.
CUPID_FIRST_STAGE_LOAD_MODULES := \
    $(strip $(shell awk \
        'NF && $$1 !~ /^\#/ && $$1 != "deferred-free-helper.ko" && \
        !seen[$$1]++ { print $$1 }' \
        "$(CUPID_FIRST_STAGE_MODULES_FILE)"))
CUPID_SECOND_STAGE_LOAD_MODULES := \
    $(strip $(shell awk \
        'NF && $$1 !~ /^\#/ && !seen[$$1]++ { print $$1 }' \
        "$(CUPID_SECOND_STAGE_MODULES_FILE)"))
CUPID_VENDOR_DLKM_EXCLUSIVE_LOAD_MODULES := \
    $(strip $(shell awk \
        'NF && $$1 !~ /^\#/ && !seen[$$1]++ { print $$1 }' \
        "$(CUPID_VENDOR_DLKM_EXCLUSIVE_MODULES_FILE)"))
ifeq ($(strip $(CUPID_FIRST_STAGE_LOAD_MODULES)),)
$(error Empty first-stage kernel module list: $(CUPID_FIRST_STAGE_MODULES_FILE))
endif
ifeq ($(strip $(CUPID_SECOND_STAGE_LOAD_MODULES)),)
$(error Empty second-stage kernel module list: $(CUPID_SECOND_STAGE_MODULES_FILE))
endif

# KeyMint starts before vendor_dlkm is mounted.  Load only the Qualcomm secure
# execution path early enough for qseecomd to register its listeners and expose
# /dev/qseecom; keep the rest of the second-stage set deferred.
CUPID_EARLY_SECURITY_LOAD_MODULES := \
    qsee_ipc_irq_bridge.ko \
    qseecom-mod.ko \
    smcinvoke_mod.ko
ifneq ($(strip $(filter-out \
    $(CUPID_SECOND_STAGE_LOAD_MODULES), \
    $(CUPID_EARLY_SECURITY_LOAD_MODULES))),)
$(error Early QSEE modules are missing from $(CUPID_SECOND_STAGE_MODULES_FILE))
endif

# Display, GPU and FastRPC services are started by the boot trigger.  Loading
# their drivers from a non-blocking vendor service lets those services race the
# creation of /dev/dri, /dev/kgsl-3d0 and /dev/fastrpc-*.  Keep the small set of
# entry-point modules in the synchronous first-stage list; modules.dep pulls in
# their provider dependencies in the kernel-defined order.
CUPID_BOOT_CRITICAL_LOAD_MODULES := \
    frpc-adsprpc.ko \
    msm_kgsl.ko \
    msm_drm.ko
ifneq ($(strip $(filter-out \
    $(CUPID_SECOND_STAGE_LOAD_MODULES), \
    $(CUPID_BOOT_CRITICAL_LOAD_MODULES))),)
$(error Boot-critical modules are missing from $(CUPID_SECOND_STAGE_MODULES_FILE))
endif
CUPID_NORMAL_FIRST_STAGE_LOAD_MODULES := \
    $(CUPID_FIRST_STAGE_LOAD_MODULES) \
    $(CUPID_EARLY_SECURITY_LOAD_MODULES) \
    $(CUPID_BOOT_CRITICAL_LOAD_MODULES) \
    mtd.ko \
    block2mtd.ko \
    mtdoops.ko

ifeq ($(strip $(CUPID_VENDOR_DLKM_EXCLUSIVE_LOAD_MODULES)),)
$(error Empty vendor_dlkm kernel module list: $(CUPID_VENDOR_DLKM_EXCLUSIVE_MODULES_FILE))
endif
CUPID_FIRST_STAGE_MODULES := $(sort $(CUPID_FIRST_STAGE_LOAD_MODULES))
CUPID_SECOND_STAGE_MODULES := $(sort $(CUPID_SECOND_STAGE_LOAD_MODULES))
CUPID_VENDOR_DLKM_EXCLUSIVE_MODULES := \
    $(sort $(CUPID_VENDOR_DLKM_EXCLUSIVE_LOAD_MODULES))
CUPID_VENDOR_RAMDISK_MODULES := \
    $(sort $(CUPID_FIRST_STAGE_MODULES) $(CUPID_SECOND_STAGE_MODULES))
CUPID_VENDOR_DLKM_MODULES := \
    $(sort \
        $(CUPID_FIRST_STAGE_MODULES) \
        $(CUPID_SECOND_STAGE_MODULES) \
        $(CUPID_VENDOR_DLKM_EXCLUSIVE_MODULES))
CUPID_VENDOR_DLKM_LOAD_MODULES := \
    $(filter-out \
        $(CUPID_EARLY_SECURITY_LOAD_MODULES) \
        $(CUPID_BOOT_CRITICAL_LOAD_MODULES), \
        $(CUPID_SECOND_STAGE_LOAD_MODULES)) \
    $(CUPID_VENDOR_DLKM_EXCLUSIVE_LOAD_MODULES)
CUPID_ALL_KERNEL_MODULES := $(CUPID_VENDOR_DLKM_MODULES)
CUPID_SOURCE_KERNEL_MODULES := \
    qcom_dma_heaps.ko
CUPID_SOURCE_KERNEL_MODULE_DIR := \
    $(PRODUCT_OUT)/obj/KLEE_KERNEL_DIST/modules
CUPID_VENDOR_RAMDISK_MODULE_PATHS := \
    $(addprefix $(CUPID_KERNEL_MODULE_DIR)/, \
        $(filter-out $(CUPID_SOURCE_KERNEL_MODULES), \
            $(CUPID_VENDOR_RAMDISK_MODULES))) \
    $(addprefix $(CUPID_SOURCE_KERNEL_MODULE_DIR)/, \
        $(filter $(CUPID_SOURCE_KERNEL_MODULES), \
            $(CUPID_VENDOR_RAMDISK_MODULES)))
CUPID_VENDOR_DLKM_MODULE_PATHS := \
    $(addprefix $(CUPID_KERNEL_MODULE_DIR)/, \
        $(filter-out $(CUPID_SOURCE_KERNEL_MODULES), \
            $(CUPID_VENDOR_DLKM_MODULES))) \
    $(addprefix $(CUPID_SOURCE_KERNEL_MODULE_DIR)/, \
        $(filter $(CUPID_SOURCE_KERNEL_MODULES), \
            $(CUPID_VENDOR_DLKM_MODULES)))

# Keep the Klee kernel target honest: every module named by the Cupid module
# manifests must be emitted by the source build. Modules whose configuration
# differs from the retained ABI kit are packaged directly from that output.
KLEE_KERNEL_MODULES += $(CUPID_ALL_KERNEL_MODULES)

# Module load lists are ordered basenames, never filesystem paths.  Keep the
# complete module set in vendor_boot so recovery can initialize the hardware
# stack, but let normal first-stage init load only the minimal Waipio providers
# needed to mount the dynamic partitions.  The remaining modules are loaded
# from vendor_dlkm after the handoff to second-stage init.
BOARD_VENDOR_RAMDISK_KERNEL_MODULES += \
    $(CUPID_VENDOR_RAMDISK_MODULE_PATHS)
BOARD_VENDOR_RAMDISK_KERNEL_MODULES_LOAD += \
    $(CUPID_NORMAL_FIRST_STAGE_LOAD_MODULES)
BOARD_VENDOR_RAMDISK_RECOVERY_KERNEL_MODULES_LOAD += \
    $(CUPID_FIRST_STAGE_LOAD_MODULES) \
    $(CUPID_SECOND_STAGE_LOAD_MODULES)
BOARD_VENDOR_KERNEL_MODULES += $(CUPID_VENDOR_DLKM_MODULE_PATHS)
BOARD_VENDOR_KERNEL_MODULES_LOAD += $(CUPID_VENDOR_DLKM_LOAD_MODULES)
BOOT_KERNEL_MODULES += $(CUPID_ALL_KERNEL_MODULES)
BOARD_VENDOR_KERNEL_MODULES_BLOCKLIST_FILE := \
    $(TARGET_KERNEL_SOURCE)/modules.vendor_blocklist.msm.waipio
BOARD_VENDOR_RAMDISK_KERNEL_MODULES_BLOCKLIST_FILE := \
    $(BOARD_VENDOR_KERNEL_MODULES_BLOCKLIST_FILE)

# Keep the stock base-DTB table separate from its matching stock DTBO.  The
# Cupid overlays are applied by the boot loader and must not be merged into the
# base payload a second time during image construction.
BOARD_PREBUILT_DTBIMAGE_DIR := $(CUPID_KERNEL_PREBUILT_DIR)/dtb

CUPID_STOCK_DTBO := vendor/xiaomi/cupid/proprietary/dtbo.img
ifneq ($(wildcard $(CUPID_STOCK_DTBO)),)
BOARD_PREBUILT_DTBOIMAGE := $(CUPID_STOCK_DTBO)
endif

# Qualcomm board fragments describe the modules that must be packaged into
# vendor_dlkm and vendor_boot. Give those fragments a stable Klee output root;
# leaving it empty turns every module into an invalid absolute path.
KERNEL_MODULES_INSTALL := dlkm
KERNEL_MODULES_OUT := out/target/product/$(PRODUCT_NAME)/$(KERNEL_MODULES_INSTALL)/lib/modules

-include $(sort $(wildcard vendor/qcom/defs/board-defs/system/*.mk))
-include $(sort $(wildcard vendor/qcom/defs/board-defs/vendor/*.mk))

# Imported Qualcomm fragments describe CodeLinaro-kernel build outputs.  Do
# not let those stale paths or load lists enter a Xiaomi SM8450 image.
BOARD_VENDOR_RAMDISK_KERNEL_MODULES := \
    $(CUPID_VENDOR_RAMDISK_MODULE_PATHS)
BOARD_VENDOR_RAMDISK_KERNEL_MODULES_LOAD := \
    $(CUPID_NORMAL_FIRST_STAGE_LOAD_MODULES)
BOARD_VENDOR_RAMDISK_RECOVERY_KERNEL_MODULES_LOAD := \
    $(CUPID_FIRST_STAGE_LOAD_MODULES) \
    $(CUPID_SECOND_STAGE_LOAD_MODULES)
BOARD_VENDOR_KERNEL_MODULES := $(CUPID_VENDOR_DLKM_MODULE_PATHS)
BOARD_VENDOR_KERNEL_MODULES_LOAD := $(CUPID_VENDOR_DLKM_LOAD_MODULES)
BOARD_VENDOR_KERNEL_MODULES_BLOCKLIST_FILE := \
    $(TARGET_KERNEL_SOURCE)/modules.vendor_blocklist.msm.waipio
BOARD_VENDOR_RAMDISK_KERNEL_MODULES_BLOCKLIST_FILE := \
    $(BOARD_VENDOR_KERNEL_MODULES_BLOCKLIST_FILE)
BOOT_KERNEL_MODULES := $(CUPID_ALL_KERNEL_MODULES)

# Android's kernel-module archive path clears the individual module variables
# later in core/config.mk.  Cupid intentionally packages its ABI-verified
# module kit file by file, so fail here instead of silently producing an empty
# or first-stage-only vendor ramdisk.
ifneq ($(strip $(BOARD_KERNEL_MODULES_ZIP)),)
$(error BOARD_KERNEL_MODULES_ZIP must be empty for the Cupid module layout)
endif
