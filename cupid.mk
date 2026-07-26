#
# Copyright (C) 2026 The KleeUI Project
#
# SPDX-License-Identifier: Apache-2.0
#

$(call inherit-product, device/xiaomi/cupid/device.mk)
$(call inherit-product, vendor/klee/build/product/common.mk)

# Use the Qualcomm Taro VINTF fragments required by the SM8450 vendor HALs.
# Keeping these declarations in the device product makes the Cupid target
# self-contained instead of inheriting the unrelated generic Taro product.
DEVICE_FRAMEWORK_MANIFEST_FILE := device/qcom/taro/framework_manifest.xml
TARGET_USES_QCV := true
DEVICE_MANIFEST_SKUS := taro
DEVICE_MANIFEST_TARO_FILES := device/qcom/taro/manifest_taro.xml
DEVICE_MATRIX_FILE := device/qcom/common/compatibility_matrix.xml

PRODUCT_NAME := cupid
PRODUCT_DEVICE := cupid
PRODUCT_BRAND := Xiaomi
PRODUCT_MANUFACTURER := Xiaomi
PRODUCT_MODEL := 2201123G

PRODUCT_SYSTEM_NAME := cupid_global
PRODUCT_SYSTEM_DEVICE := cupid
PRODUCT_SYSTEM_BRAND := Xiaomi
PRODUCT_SYSTEM_MANUFACTURER := Xiaomi
PRODUCT_SYSTEM_MODEL := 2201123G

PRODUCT_CHARACTERISTICS := nosdcard
PRODUCT_GMS_CLIENTID_BASE := android-xiaomi
