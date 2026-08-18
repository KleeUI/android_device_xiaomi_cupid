#
# Copyright (C) 2026 The KleeUI Project
#
# SPDX-License-Identifier: Apache-2.0
#

DEVICE_PATH := device/xiaomi/cupid

# Put Cupid's AudioReach interface list before inherited Qualcomm product
# fragments.  PRODUCT_COPY_FILES keeps the first entry for a destination and
# records later duplicates as overrides, so this device-owned list wins over
# the generic Taro copy rule without modifying the shared platform tree.
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/configs/audio/vendor_audio_interfaces.xml:vendor/etc/vendor_audio_interfaces.xml

BOARD_AVB_ENABLE := true

# The stock SM8450 GPU userspace is paired with Qualcomm's gralloc4 private
# handle ABI.  Define this before any inherited Qualcomm product fragment so
# the AIDL allocator and mapper5 packages are never added to this product.
TARGET_QTI_GRALLOC4_COMPAT := true

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
# The Xiaomi kernel build already owns every module in these manifests.  Do
# not inherit CodeLinaro's parallel DLKM packages: inherited product variables
# are resolved after this file is parsed, so filtering PRODUCT_PACKAGES at the
# end is too late to prevent their kernel_platform rules from entering droid.
_cupid_qcom_kernel_product_defs := \
    vendor/qcom/defs/product-defs/vendor/audio_kernel_product_board.mk \
    vendor/qcom/defs/product-defs/vendor/bt_kernel_product_board.mk \
    vendor/qcom/defs/product-defs/vendor/camera-kernel_product.mk \
    vendor/qcom/defs/product-defs/vendor/data_dlkm_vendor_product.mk \
    vendor/qcom/defs/product-defs/vendor/dataipa_dlkm_vendor_product.mk \
    vendor/qcom/defs/product-defs/vendor/datarmnet_dlkm_vendor_product.mk \
    vendor/qcom/defs/product-defs/vendor/datarmnet_ext_dlkm_vendor_product.mk \
    vendor/qcom/defs/product-defs/vendor/display_driver_product.mk \
    vendor/qcom/defs/product-defs/vendor/dsp_kernel_product.mk \
    vendor/qcom/defs/product-defs/vendor/mm_driver_product.mk \
    vendor/qcom/defs/product-defs/vendor/mmrm_kernel_product.mk \
    vendor/qcom/defs/product-defs/vendor/securemsm_kernel_product_board.mk \
    vendor/qcom/defs/product-defs/vendor/spu_driver_product.mk \
    vendor/qcom/defs/product-defs/vendor/synx_kernel_product.mk \
    vendor/qcom/defs/product-defs/vendor/touch_driver_product.mk \
    vendor/qcom/defs/product-defs/vendor/video_kernel_product.mk
_cupid_qcom_vendor_defs := $(filter-out \
    $(_cupid_qcom_kernel_product_defs), \
    $(sort $(wildcard vendor/qcom/defs/product-defs/vendor/*.mk)))
$(foreach definition,$(_cupid_qcom_system_defs), \
    $(call inherit-product,$(definition)))
$(foreach definition,$(_cupid_qcom_vendor_defs), \
    $(call inherit-product,$(definition)))
_cupid_qcom_system_defs :=
_cupid_qcom_vendor_defs :=
_cupid_qcom_kernel_product_defs :=

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
    $(DEVICE_PATH)/rootdir/etc/fstab.qcom:$(TARGET_COPY_OUT_VENDOR)/etc/fstab.qcom \
    $(DEVICE_PATH)/rootdir/etc/fstab.qcom:$(TARGET_COPY_OUT_RECOVERY)/root/first_stage_ramdisk/fstab.qcom \
    $(DEVICE_PATH)/recovery.posix.fstab:$(TARGET_COPY_OUT_RECOVERY)/root/system/etc/fstab \
    vendor/xiaomi/cupid/proprietary/vendor/firmware/st_fts_l3.ftb:$(TARGET_COPY_OUT_RECOVERY)/root/lib/firmware/st_fts_l3.ftb \
    vendor/xiaomi/cupid/proprietary/vendor/firmware/stm_fts_production_limits.csv:$(TARGET_COPY_OUT_RECOVERY)/root/lib/firmware/stm_fts_production_limits.csv \
    $(DEVICE_PATH)/rootdir/bin/klee-wait-write.sh:$(TARGET_COPY_OUT_VENDOR)/bin/klee-wait-write.sh \
    $(DEVICE_PATH)/rootdir/etc/init/gatekeeper-qti.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/gatekeeper-qti.rc \
    $(DEVICE_PATH)/rootdir/etc/init/android.hardware.security.keymint-service-qti.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/android.hardware.security.keymint-service-qti.rc \
    $(DEVICE_PATH)/rootdir/etc/init/init.qti.kernel.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.qti.kernel.rc \
    $(DEVICE_PATH)/rootdir/etc/modules.load.cupid:$(TARGET_COPY_OUT_VENDOR_DLKM)/lib/modules/modules.load.cupid \
    $(DEVICE_PATH)/rootdir/etc/init/qseecomd.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/qseecomd.rc \
    device/qcom/taro/init.target.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/hw/init.target.rc \
    device/qcom/taro/ueventd-odm.rc:$(TARGET_COPY_OUT_ODM)/etc/ueventd.rc

PRODUCT_PACKAGES += \
    CupidFrameworksResOverlay \
    android.hardware.boot-service.qti \
    android.hardware.boot-service.qti.recovery \
    android.hardware.security.rkp-V3-ndk.vendor \
    cupid_bt_firmware_mountpoint \
    cupid_dsp_mountpoint \
    cupid_firmware_mnt_mountpoint \
    cupid_framework_compatibility_matrix.6.xml \
    cupid_qca6490_amss20_firmware \
    cupid_qca6490_bdwlan_firmware \
    cupid_qca6490_wifi_config \
    cupid_qca6490_wlan_mac \
    cupid_vm_system_mountpoint \
    fastbootd \
    update_engine \
    update_verifier

PRODUCT_VENDOR_PROPERTIES += \
    ro.soc.manufacturer=QTI \
    ro.soc.model=SM8450 \
    vendor.display.disable_sdm_plugins=1

# Proprietary Xiaomi/QTI components are intentionally isolated from the device
# integration and can be populated from a user-owned stock installation.
$(call inherit-product-if-exists, vendor/xiaomi/sm8450-common/sm8450-common-vendor.mk)
$(call inherit-product-if-exists, vendor/xiaomi/sm8450-common/klee-compat/klee-compat.mk)
$(call inherit-product-if-exists, vendor/xiaomi/cupid/cupid-vendor.mk)

# Cupid uses the stock, ABI-matched AudioReach HIDL runtime.  The generic
# Qualcomm product fragments also describe the legacy AIDL bridge; remove those
# entries and explicitly install the matching HIDL service and libraries.
PRODUCT_PACKAGES := $(filter-out libagmservice libagmipcservice libpalipcservice,$(PRODUCT_PACKAGES))
PRODUCT_PACKAGES += \
    libar-acdb \
    libar-gpr \
    libar-gsl \
    libar-pal \
    libagm \
    libagmclient \
    libagm_compress_plugin \
    libagm_mixer_plugin \
    libagm_pcm_plugin \
    libagmmixer \
    libaudioroute_ext \
    libxlog \
    libaudio_log_utils \
    libats \
    libdiag \
    libmisight \
    libpdmapper \
    libpdnotifier \
    liblx-ar_util \
    liblx-osal \
    libpalclient \
    vendor.qti.hardware.AGMIPC@1.0 \
    vendor.qti.hardware.AGMIPC@1.0-impl \
    vendor.qti.hardware.AGMIPC@1.0-service \
    vendor.qti.hardware.AGMIPC@1.0-service.rc \
    vendor.qti.hardware.pal@1.0 \
    vendor.qti.hardware.pal@1.0-impl


# The Qualcomm product fragments above expose CodeLinaro-built DLKM modules as
# Android packages. Cupid assembles the verified SM8450 module manifests from
# BoardConfig instead, so never invoke the obsolete kernel_platform builders.
PRODUCT_PACKAGES := $(filter-out %.ko,$(PRODUCT_PACKAGES))
PRODUCT_PACKAGES_DEBUG := $(filter-out %.ko,$(PRODUCT_PACKAGES_DEBUG))
PRODUCT_PACKAGES_ENG := $(filter-out %.ko,$(PRODUCT_PACKAGES_ENG))
