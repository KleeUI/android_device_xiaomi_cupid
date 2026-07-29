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
BOARD_RAMDISK_USE_LZ4 := true
BOARD_INCLUDE_DTB_IN_BOOTIMG := true
BOARD_INCLUDE_RECOVERY_DTBO := true

BOARD_KERNEL_CMDLINE := \
    disable_dma32=on \
    mtdoops.fingerprint=Klee-1.0

BOARD_BOOTCONFIG := \
    androidboot.hardware=qcom \
    androidboot.memcg=1 \
    androidboot.usbcontroller=a600000.dwc3

TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/recovery.fstab

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
TARGET_KERNEL_SOURCE := kernel_platform/msm-kernel
TARGET_KERNEL_PLATFORM_PATH := kernel_platform
TARGET_KERNEL_BUILD_CONFIG := common/build.config.msm.waipio
TARGET_NEEDS_DTBOIMAGE := true
KLEE_KERNEL_DTBO_TARGET := dtbo.img

# The Waipio GKI keeps storage, clocks, regulators, interrupt routing and
# IOMMU support modular. These modules must be available before first-stage
# init can discover UFS and mount the dynamic partitions. The kernel platform
# build publishes them at the root of KLEE_KERNEL_DIST.
CUPID_FIRST_STAGE_MODULES_FILE := \
    $(TARGET_KERNEL_SOURCE)/modules.list.msm.waipio
CUPID_FIRST_STAGE_MODULES := \
    $(filter-out \
        deferred-free-helper.ko, \
        $(strip $(shell cat $(CUPID_FIRST_STAGE_MODULES_FILE))))
CUPID_FIRST_STAGE_MODULE_PATHS := \
    $(addprefix $(PRODUCT_OUT)/obj/KLEE_KERNEL_DIST/,$(CUPID_FIRST_STAGE_MODULES))
KLEE_KERNEL_MODULES += $(CUPID_FIRST_STAGE_MODULES)
BOARD_VENDOR_RAMDISK_KERNEL_MODULES += $(CUPID_FIRST_STAGE_MODULE_PATHS)
BOARD_VENDOR_RAMDISK_KERNEL_MODULES_LOAD += $(CUPID_FIRST_STAGE_MODULE_PATHS)
BOARD_VENDOR_RAMDISK_RECOVERY_KERNEL_MODULES_LOAD += $(CUPID_FIRST_STAGE_MODULE_PATHS)

# CodeLinaro's public Waipio 5.10 release omits the retail board device-tree
# repository. Use DTB and DTBO inputs extracted from matching stock firmware
# when they are available locally; these proprietary inputs are deliberately
# not source-hosted.
CUPID_STOCK_DTB_DIR := vendor/xiaomi/cupid/proprietary/dtb
CUPID_STOCK_DTBO := vendor/xiaomi/cupid/proprietary/dtbo.img
ifneq ($(wildcard $(CUPID_STOCK_DTB_DIR)/*.dtb),)
BOARD_PREBUILT_DTBIMAGE_DIR := $(CUPID_STOCK_DTB_DIR)
endif
ifneq ($(wildcard $(CUPID_STOCK_DTBO)),)
BOARD_PREBUILT_DTBOIMAGE := $(CUPID_STOCK_DTBO)
KLEE_KERNEL_SKIP_PLATFORM_DTBO := true
endif

# Qualcomm board fragments describe the modules that must be packaged into
# vendor_dlkm and vendor_boot. Give those fragments a stable Klee output root;
# leaving it empty turns every module into an invalid absolute path.
KERNEL_MODULES_INSTALL := dlkm
KERNEL_MODULES_OUT := out/target/product/$(PRODUCT_NAME)/$(KERNEL_MODULES_INSTALL)/lib/modules

-include $(sort $(wildcard vendor/qcom/defs/board-defs/system/*.mk))
-include $(sort $(wildcard vendor/qcom/defs/board-defs/vendor/*.mk))
