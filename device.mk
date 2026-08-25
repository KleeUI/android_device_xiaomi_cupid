#
# Copyright (C) 2026 The KleeUI Project
#
# SPDX-License-Identifier: Apache-2.0
#

DEVICE_PATH := device/xiaomi/cupid

# Cupid's proprietary Codec2 service is described by the Taro registry. Put
# the complete device registry first so Qualcomm's QMAA fallback cannot claim
# the active media_codecs.xml destination with its legacy OMX-only table.
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/configs/media/media_codecs.xml:$(TARGET_COPY_OUT_VENDOR)/etc/media_codecs.xml

# Put Cupid's AudioReach configuration before inherited Qualcomm product
# fragments. PRODUCT_COPY_FILES keeps the first entry for a destination, so
# these device-owned files win over generic Taro rules without changing the
# shared platform configuration used by other Qualcomm devices.
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/configs/audio/vendor_audio_interfaces.xml:vendor/etc/vendor_audio_interfaces.xml \
    $(DEVICE_PATH)/configs/audio/usecaseKvManager.xml:vendor/etc/usecaseKvManager.xml \
    $(DEVICE_PATH)/configs/audio/sku_taro/resourcemanager_waipio_mtp.xml:vendor/etc/audio/sku_taro/resourcemanager_waipio_mtp.xml

BOARD_AVB_ENABLE := true

# Cupid's proprietary CamX and Adreno userspace consume Qualcomm's gralloc4
# private-handle ABI, so keep the matching HIDL allocator and mapper4 services.
# AOSP 17 clients use the AIDL allocator frontend as well; both frontends use
# the same legacy private-handle backend and must be packaged together.
TARGET_QTI_GRALLOC4_COMPAT := true

# Cupid uses the dedicated, non-slot FRP partition rather than Qualcomm's
# legacy vendor-common fallback to the config partition.
BOARD_FRP_PARTITION_NAME := frp

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

# Keep the stock RFS completion marker as an empty, device-owned file. The
# topology itself is generated below from source install_symlink modules.
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/configs/rfs/rfs_symlinks:$(TARGET_COPY_OUT_VENDOR)/rfs/rfs_symlinks

# Expose remote-processor state through the exact Cupid RFS topology. These
# modules install only symbolic links; calibration and firmware payloads stay
# on persist, data, and their dedicated firmware partitions.
PRODUCT_PACKAGES += \
    cupid_rfs_msm_adsp_hlos \
    cupid_rfs_msm_adsp_ramdumps \
    cupid_rfs_msm_adsp_readonly_firmware \
    cupid_rfs_msm_adsp_readonly_vendor_firmware \
    cupid_rfs_msm_adsp_readwrite \
    cupid_rfs_msm_adsp_shared \
    cupid_rfs_msm_cdsp_hlos \
    cupid_rfs_msm_cdsp_ramdumps \
    cupid_rfs_msm_cdsp_readonly_firmware \
    cupid_rfs_msm_cdsp_readonly_vendor_firmware \
    cupid_rfs_msm_cdsp_readwrite \
    cupid_rfs_msm_cdsp_shared \
    cupid_rfs_msm_mpss_hlos \
    cupid_rfs_msm_mpss_ramdumps \
    cupid_rfs_msm_mpss_readonly_firmware \
    cupid_rfs_msm_mpss_readonly_vendor_firmware \
    cupid_rfs_msm_mpss_readwrite \
    cupid_rfs_msm_mpss_shared \
    cupid_rfs_msm_slpi_hlos \
    cupid_rfs_msm_slpi_ramdumps \
    cupid_rfs_msm_slpi_readonly_firmware \
    cupid_rfs_msm_slpi_readonly_vendor_firmware \
    cupid_rfs_msm_slpi_readwrite \
    cupid_rfs_msm_slpi_shared \
    cupid_rfs_msm_wpss_hlos \
    cupid_rfs_msm_wpss_ramdumps \
    cupid_rfs_msm_wpss_readonly_firmware \
    cupid_rfs_msm_wpss_readonly_vendor_firmware \
    cupid_rfs_msm_wpss_readwrite \
    cupid_rfs_msm_wpss_shared \
    cupid_rfs_mdm_adsp_hlos \
    cupid_rfs_mdm_adsp_ramdumps \
    cupid_rfs_mdm_adsp_readonly_firmware \
    cupid_rfs_mdm_adsp_readonly_vendor_firmware \
    cupid_rfs_mdm_adsp_readwrite \
    cupid_rfs_mdm_adsp_shared \
    cupid_rfs_mdm_cdsp_hlos \
    cupid_rfs_mdm_cdsp_ramdumps \
    cupid_rfs_mdm_cdsp_readonly_firmware \
    cupid_rfs_mdm_cdsp_readonly_vendor_firmware \
    cupid_rfs_mdm_cdsp_readwrite \
    cupid_rfs_mdm_cdsp_shared \
    cupid_rfs_mdm_mpss_hlos \
    cupid_rfs_mdm_mpss_ramdumps \
    cupid_rfs_mdm_mpss_readonly_firmware \
    cupid_rfs_mdm_mpss_readonly_vendor_firmware \
    cupid_rfs_mdm_mpss_readwrite \
    cupid_rfs_mdm_mpss_shared \
    cupid_rfs_mdm_slpi_hlos \
    cupid_rfs_mdm_slpi_ramdumps \
    cupid_rfs_mdm_slpi_readonly_firmware \
    cupid_rfs_mdm_slpi_readonly_vendor_firmware \
    cupid_rfs_mdm_slpi_readwrite \
    cupid_rfs_mdm_slpi_shared \
    cupid_rfs_mdm_tn_hlos \
    cupid_rfs_mdm_tn_ramdumps \
    cupid_rfs_mdm_tn_readonly_firmware \
    cupid_rfs_mdm_tn_readonly_vendor_firmware \
    cupid_rfs_mdm_tn_readwrite \
    cupid_rfs_mdm_tn_shared \
    cupid_rfs_mdm_wpss_hlos \
    cupid_rfs_mdm_wpss_ramdumps \
    cupid_rfs_mdm_wpss_readonly_firmware \
    cupid_rfs_mdm_wpss_readonly_vendor_firmware \
    cupid_rfs_mdm_wpss_readwrite \
    cupid_rfs_mdm_wpss_shared \
    cupid_rfs_apq_gnss_hlos \
    cupid_rfs_apq_gnss_ramdumps \
    cupid_rfs_apq_gnss_readonly_firmware \
    cupid_rfs_apq_gnss_readonly_vendor_firmware \
    cupid_rfs_apq_gnss_readwrite \
    cupid_rfs_apq_gnss_shared

# Publish only capabilities backed by Cupid's physical hardware and packaged
# HALs.  These are upstream AOSP declarations; the device tree owns only their
# placement in the vendor image.
PRODUCT_COPY_FILES += \
    frameworks/native/data/etc/android.hardware.bluetooth_le.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.bluetooth_le.xml \
    frameworks/native/data/etc/android.hardware.sensor.gyroscope.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.sensor.gyroscope.xml \
    frameworks/native/data/etc/android.hardware.sensor.light.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.sensor.light.xml \
    frameworks/native/data/etc/android.hardware.sensor.proximity.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.sensor.proximity.xml \
    frameworks/native/data/etc/android.hardware.sensor.stepcounter.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.sensor.stepcounter.xml \
    frameworks/native/data/etc/android.hardware.telephony.cdma.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.telephony.cdma.xml \
    frameworks/native/data/etc/android.hardware.telephony.gsm.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.telephony.gsm.xml \
    frameworks/native/data/etc/android.hardware.telephony.ims.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.telephony.ims.xml \
    frameworks/native/data/etc/android.software.sip.voip.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.software.sip.voip.xml

# The proprietary graphics stack keeps the legacy allocator/gralloc4 ABI, but
# AOSP 17 clients load the stable Mapper5 entry point. Package Klee's Mapper5
# compatibility bridge explicitly; Qualcomm's generic display fragment omits
# it whenever TARGET_QTI_GRALLOC4_COMPAT is enabled.
PRODUCT_PACKAGES += \
    CupidFrameworksResOverlay \
    android.hardware.audio.parameter_parser.example_service \
    android.hardware.boot-service.qti \
    android.hardware.boot-service.qti.recovery \
    android.hardware.sensors-service.multihal \
    android.hardware.security.rkp-V3-ndk.vendor \
    android.hardware.wifi-service \
    cupid_bt_firmware_mountpoint \
    cupid_dsp_mountpoint \
    cupid_firmware_mnt_mountpoint \
    cupid_framework_compatibility_matrix.6.xml \
    cupid_qca6490_amss20_firmware \
    cupid_qca6490_bdwlan_firmware \
    cupid_qca6490_board_firmware \
    cupid_qca6490_m3_firmware \
    cupid_qca6490_regdb_firmware \
    cupid_qca6490_wifi_config \
    cupid_qca6490_wlan_mac \
    cupid_vm_system_mountpoint \
    fastbootd \
    hostapd \
    hostapd_cli \
    mapper.qti \
    qcrilNrDb_vendor \
    vendor.qti.hardware.display.allocator-service \
    wpa_supplicant \
    update_engine \
    update_engine_sideload \
    update_verifier

# Qualcomm's common product already selects the system_ext HIDL wrapper and
# telephony utilities plus the product IMS extension from the upstream tree.
# Add the remaining system_ext API and product wrapper required by Xiaomi's
# radio applications.
PRODUCT_PACKAGES += \
    extphonelib \
    extphonelib.xml \
    qti-telephony-hidl-wrapper-prd \
    qti_telephony_hidl_wrapper_prd.xml

PRODUCT_VENDOR_PROPERTIES += \
    ro.soc.manufacturer=QTI \
    ro.soc.model=SM8450 \
    vendor.display.disable_sdm_plugins=1

# Proprietary Xiaomi/QTI components are intentionally isolated from the device
# integration and can be populated from a user-owned stock installation.
$(call inherit-product-if-exists, vendor/xiaomi/sm8450-common/sm8450-common-vendor.mk)
$(call inherit-product, device/xiaomi/cupid/klee-compat.mk)
$(call inherit-product-if-exists, vendor/xiaomi/cupid/cupid-vendor.mk)

# Cupid uses the stock, ABI-matched AudioReach HIDL runtime.  The generic
# Qualcomm product fragments also describe the legacy AIDL bridge; remove those
# entries and explicitly install the matching HIDL service and libraries.
PRODUCT_PACKAGES := $(filter-out \
    libagmservice libagmservice:% \
    libagmipcservice libagmipcservice:% \
    libpalipcservice libpalipcservice:%, \
    $(PRODUCT_PACKAGES))
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
    libaudio_log_utils \
    libaudioroute_ext \
    libxlog \
    libats \
    libdiag \
    libmisight \
    libpdmapper \
    libpdnotifier \
    libsndcardparser \
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
