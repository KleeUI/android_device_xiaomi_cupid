#!/system/bin/sh
#
# Copyright (C) 2026 The KleeUI Project
#
# SPDX-License-Identifier: Apache-2.0
#

module_dir=/vendor/lib/modules
load_file="${module_dir}/modules.load"

if [ ! -r "${load_file}" ]; then
    /system/bin/log -p e -t KleeModules \
        "Deferred module manifest is missing: ${load_file}"
    /system/bin/setprop vendor.all.modules.ready 0
    exit 1
fi

if [ ! -s "${load_file}" ]; then
    /system/bin/log -p e -t KleeModules \
        "Deferred module manifest is empty: ${load_file}"
    /system/bin/setprop vendor.all.modules.ready 0
    exit 1
fi

# Android's modprobe accepts a modules.load manifest through --all.  It resolves
# dependencies and treats modules already loaded by first-stage init as
# successful, while keeping the complete manifest in one process.
if ! /system/bin/modprobe -d "${module_dir}" --all="${load_file}"; then
    /system/bin/log -p e -t KleeModules \
        "One or more deferred kernel modules failed to load"
    /system/bin/setprop vendor.all.modules.ready 0
    exit 1
fi

/system/bin/setprop vendor.all.modules.ready 1
/system/bin/log -p i -t KleeModules "Deferred kernel modules are ready"
