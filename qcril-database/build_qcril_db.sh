#!/bin/sh
# Copyright (C) 2026 The KleeUI Project
# SPDX-License-Identifier: Apache-2.0

set -eu

if [ "$#" -lt 3 ]; then
    echo "usage: $0 SQLITE OUTPUT SQL..." >&2
    exit 2
fi

sqlite="$1"
output="$2"
shift 2

apply_migration() {
    wanted="$1"
    shift
    found=""

    for input do
        if [ "${input##*/}" = "$wanted" ]; then
            if [ -n "$found" ]; then
                echo "duplicate qcril migration: $wanted" >&2
                exit 1
            fi
            found="$input"
        fi
    done

    if [ -z "$found" ]; then
        echo "missing qcril migration: $wanted" >&2
        exit 1
    fi

    "$sqlite" -bail "$output" < "$found"
}

rm -f "$output"

for migration in \
    0_initial_qcrilnr.sql \
    1_version_intro_qcrilnr.sql \
    2_version_add_wps_config_qcrilnr.sql \
    3_version_update_wps_config_qcrilnr.sql \
    4_version_update_ecc_table_qcrilnr.sql \
    5_version_update_ecc_table_qcrilnr.sql \
    6_version_change_property_table_qcrilnr.sql \
    7_version_update_ecc_table_qcrilnr.sql \
    8_version_update_ecc_table.sql \
    9_version_update_ecc_table.sql \
    10_version_update_ecc_table.sql \
    11_version_update_ecc_table.sql \
    12_version_update_ecc_table.sql \
    6.0_config.sql \
    7.0_config.sql \
    8.0_config.sql \
    9.0_config.sql \
    10.0_config.sql \
    11.0_config.sql \
    12.0_config.sql \
    13.0_config.sql \
    14.0_config.sql \
    klee_radio_defaults.sql \
    16.0_config.sql
do
    apply_migration "$migration" "$@"
done

integrity="$("$sqlite" -batch "$output" 'PRAGMA integrity_check;')"
if [ "$integrity" != "ok" ]; then
    echo "qcril database integrity check failed: $integrity" >&2
    exit 1
fi
