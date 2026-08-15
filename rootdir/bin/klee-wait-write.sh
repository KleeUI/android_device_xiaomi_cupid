#!/vendor/bin/sh
# Copyright (C) 2026 The KleeUI Project
# SPDX-License-Identifier: Apache-2.0

target="$1"
value="$2"
remaining="${3:-60}"

if [ -z "$target" ] || [ -z "$value" ]; then
    exit 2
fi

while [ "$remaining" -gt 0 ]; do
    if [ -e "$target" ]; then
        printf '%s' "$value" > "$target"
        exit $?
    fi

    sleep 1
    remaining=$((remaining - 1))
done

exit 1
