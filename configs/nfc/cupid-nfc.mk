# Copyright (C) 2026 The KleeUI Project
# SPDX-License-Identifier: Apache-2.0

# The current NXP source module owns its init and AIDL VINTF fragments.
# Keep Cupid's existing SN100U configuration and firmware providers.
PRODUCT_PACKAGES += android.hardware.nfc-service.nxp

# NFC hardware is present. Additional SE and card-emulation capabilities
# remain subject to their separate product integration and validation.
PRODUCT_COPY_FILES += \
    frameworks/native/data/etc/android.hardware.nfc.xml:$(TARGET_COPY_OUT_VENDOR)/etc/permissions/android.hardware.nfc.xml
