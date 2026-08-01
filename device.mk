#
# Copyright (C) 2026 The KleeUI Project
#
# SPDX-License-Identifier: Apache-2.0
#

DEVICE_PATH := device/xiaomi/cupid

BOARD_AVB_ENABLE := true

$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base_telephony.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/emulated_storage.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/virtual_ab_ota.mk)
$(call inherit-product, device/qcom/vendor-common/common64.mk)
$(call inherit-product, frameworks/native/build/phone-xhdpi-6144-dalvik-heap.mk)

TARGET_BOARD_PLATFORM := taro
TARGET_USES_QMAA := false
TARGET_USES_QCOM_BSP := true
TARGET_USES_PREBUILT_AUDIOREACH_GRAPH_SERVICES := true
$(call soong_config_set,klee_rmnetctl,legacy_driver,true)
ENABLE_AB := true
ENABLE_VIRTUAL_AB := true
BUILD_DISPLAY_TECHPACK_SOURCE := true
BUILD_DISPLAY_TECHPACK_SOURCE_VARIANT := true

# Qualcomm product fragments name their DLKM packages using this path while
# product configuration is evaluated, before BoardConfig values are visible.
KERNEL_MODULES_INSTALL := dlkm
KERNEL_MODULES_OUT := \
    out/target/product/$(TARGET_PRODUCT)/$(KERNEL_MODULES_INSTALL)/lib/modules

# Import the pinned CodeLinaro platform definitions without inheriting its
# vendor-only taro product or legacy global board assignments.
_cupid_qcom_system_defs := $(sort \
    $(wildcard vendor/qcom/defs/product-defs/system/*.mk))
_cupid_qcom_vendor_defs := $(sort \
    $(wildcard vendor/qcom/defs/product-defs/vendor/*.mk))
$(foreach definition,$(_cupid_qcom_system_defs), \
    $(call inherit-product,$(definition)))
$(foreach definition,$(_cupid_qcom_vendor_defs), \
    $(call inherit-product,$(definition)))

include device/qcom/wlan/taro/wlan.mk

# Build a complete Klee product.
PRODUCT_BUILD_SYSTEM_IMAGE := true
PRODUCT_BUILD_SYSTEM_EXT_IMAGE := true
PRODUCT_BUILD_PRODUCT_IMAGE := true
PRODUCT_BUILD_VENDOR_IMAGE := true
PRODUCT_BUILD_ODM_IMAGE := true
PRODUCT_BUILD_VENDOR_DLKM_IMAGE := true
PRODUCT_BUILD_BOOT_IMAGE := true
PRODUCT_BUILD_VENDOR_BOOT_IMAGE := true
PRODUCT_BUILD_RECOVERY_IMAGE := true
PRODUCT_BUILD_VBMETA_IMAGE := true
PRODUCT_BUILD_SUPER_PARTITION := true
TARGET_SKIP_OTA_PACKAGE := false

PRODUCT_USE_DYNAMIC_PARTITIONS := true
PRODUCT_ENFORCE_RRO_TARGETS := *
PRODUCT_SHIPPING_API_LEVEL := 32
BOARD_SHIPPING_API_LEVEL := 31

PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/rootdir/etc/fstab.qcom:$(TARGET_COPY_OUT_VENDOR_RAMDISK)/first_stage_ramdisk/fstab.qcom \
    device/qcom/taro/init.target.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.target.rc \
    device/qcom/taro/ueventd-odm.rc:$(TARGET_COPY_OUT_ODM)/etc/ueventd.rc

PRODUCT_PACKAGES += \
    CupidFrameworksResOverlay \
    cupid_framework_compatibility_matrix.6.xml \
    fastbootd \
    update_engine \
    update_verifier

PRODUCT_VENDOR_PROPERTIES += \
    ro.soc.manufacturer=QTI \
    ro.soc.model=SM8450

# Proprietary Xiaomi/QTI components are intentionally isolated from the device
# integration and can be populated from a user-owned stock installation.
$(call inherit-product-if-exists, vendor/xiaomi/sm8450-common/sm8450-common-vendor.mk)
$(call inherit-product-if-exists, vendor/xiaomi/sm8450-common/klee-compat/klee-compat.mk)
$(call inherit-product-if-exists, vendor/xiaomi/cupid/cupid-vendor.mk)

# The Qualcomm product fragments above expose CodeLinaro-built DLKM modules as
# Android packages. Cupid assembles the verified SM8450 module manifests from
# BoardConfig instead, so never invoke the obsolete kernel_platform builders.
PRODUCT_PACKAGES := $(filter-out %.ko,$(PRODUCT_PACKAGES))
PRODUCT_PACKAGES_DEBUG := $(filter-out %.ko,$(PRODUCT_PACKAGES_DEBUG))
PRODUCT_PACKAGES_ENG := $(filter-out %.ko,$(PRODUCT_PACKAGES_ENG))
