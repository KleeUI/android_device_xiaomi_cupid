#
# Copyright (C) 2026 The KleeUI Project
#
# SPDX-License-Identifier: Apache-2.0
#

$(call inherit-product, device/xiaomi/cupid/device.mk)
$(call inherit-product, vendor/klee/build/product/common.mk)

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
