#
# Copyright (C) 2026 The KleeUI Project
#
# SPDX-License-Identifier: Apache-2.0
#

PRODUCT_PACKAGES += \
    android.media.audio.common.types-V4-cpp \
    audio_dynamic_log.xml \
    cupid_libkeymint_ndk_platform \
    cupid_libsecureclock_ndk_platform \
    cupid_libsharedsecret_ndk_platform \
    libagm \
    libar-pal \
    libar-acdb \
    libats \
    libhidlbase_shim \
    libjson \
    liblx-osal \
    libprotobuf-cpp-full-21.7 \
    libtinyxml2-v34 \
    com.dsi.ant@1.0 \
    QtiTelephonyBroadcastCompat \
    QtiTelephonyCompat \
    vendor.qti.hardware.btconfigstore@1.0 \
    vendor.qti.hardware.btconfigstore@2.0 \
    vendor.qti.hardware.capabilityconfigstore@1.0 \
    vendor.qti.hardware.perf@2.0 \
    vendor.qti.hardware.perf@2.1 \
    vendor.qti.hardware.perf@2.2 \
    vendor.qti.hardware.perf@2.3 \
    vendor.xiaomi.hardware.fx.tunnel@1.0 \
    vendor.xiaomi.hardware.mlipay@1.0 \
    vendor.xiaomi.hardware.mlipay@1.1 \
    vendor.xiaomi.hardware.mtdservice@1.0

# Xiaomi's Qualcomm telephony applications resolve this framework-facing API
# from the boot class path rather than through an APK class loader.
PRODUCT_BOOT_JARS_EXTRA += \
    system_ext:QtiTelephonyCompat
