#!/usr/bin/env python3
# Copyright (C) 2026 The KleeUI Project
# SPDX-License-Identifier: Apache-2.0
"""Behavioral regression tests for the source ownership preflight.

Run from the device repository with:
    python -m unittest discover -s tests -p test_source_build_contract.py -v
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest


CHECKER_PATH = (Path(__file__).resolve().parents[1] / "tools"
                / "check_source_build_contract.py")
SPEC = importlib.util.spec_from_file_location("source_contract", CHECKER_PATH)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


class SourceBuildContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cupid-source-contract-")
        self.addCleanup(self.temporary.cleanup)
        self.top = Path(self.temporary.name)
        self.root = "vendor/qcom/opensource/runtime"
        self.source_file = self.root + "/Android.bp"
        self.vendor_file = "vendor/xiaomi/test/Android.bp"
        self.device_file = "device/xiaomi/cupid/device.mk"
        self.contract = {
            "version": 1,
            "source_built": [{
                "name": "test-runtime",
                "root": self.root,
                "modules": [{"name": "libcupid_runtime", "file": "Android.bp",
                             "type": "cc_library_shared"}],
            }],
            "product_checks": [{
                "file": self.device_file,
                "assignments": {"TARGET_USES_PREBUILT_RUNTIME": "false"},
                "contains": ["libcupid_runtime"],
            }],
            "vendor_metadata": [self.vendor_file],
        }
        self.write(self.source_file, '''
cc_library_shared {
    name: "libcupid_runtime",
    vendor: true,
    srcs: ["runtime.cpp"],
}
''')
        self.write(self.root + "/runtime.cpp", "int runtime() { return 1; }\n")
        self.write(self.device_file, "TARGET_USES_PREBUILT_RUNTIME := false\n"
                   "PRODUCT_PACKAGES += libcupid_runtime\n")
        self.write(self.vendor_file, "soong_namespace {}\n")

    def write(self, relative, text):
        path = self.top / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def errors(self, module_info=None, contract=None):
        return checker.validate(self.top, contract or self.contract, module_info)

    def assert_failure(self, expected, module_info=None, contract=None):
        errors = self.errors(module_info, contract)
        self.assertTrue(errors, "invalid source configuration was accepted")
        self.assertTrue(any(expected in error for error in errors), errors)

    def test_valid_source_with_normalized_vendor_is_accepted(self):
        self.assertEqual(self.errors(), [])

    def test_missing_tree_is_not_treated_as_an_optional_runtime(self):
        contract = copy.deepcopy(self.contract)
        contract["source_built"][0]["root"] = "vendor/qcom/opensource/missing"
        self.assert_failure("missing source tree", contract=contract)

    def test_empty_source_directory_is_not_enough(self):
        (self.top / self.source_file).unlink()
        self.assert_failure("missing definition")

    def test_required_source_input_is_checked(self):
        contract = copy.deepcopy(self.contract)
        contract["source_built"][0]["required_files"] = ["required.h"]
        self.assert_failure("missing source input", contract=contract)

    def test_comments_cannot_supply_a_module_definition(self):
        self.write(self.source_file, '''
// cc_library_shared { name: "libcupid_runtime", srcs: ["runtime.cpp"], }
/* cc_library_shared { name: "libcupid_runtime", srcs: ["runtime.cpp"], } */
cc_library_shared { name: "another_runtime", srcs: ["runtime.cpp"], }
''')
        self.assert_failure("expected one definition")

    def test_nested_name_cannot_rename_its_parent_module(self):
        self.write(self.source_file, '''
cc_library_shared {
    name: "another_runtime",
    target: { android: { name: "libcupid_runtime", }, },
    srcs: ["runtime.cpp"],
}
''')
        self.assert_failure("expected one definition")

    def test_strings_with_comment_markers_do_not_unbalance_module_blocks(self):
        self.write(self.source_file, '''
cc_library_shared {
    name: "libcupid_runtime",
    cflags: ["-DEXAMPLE_URL=\\\"https://example.invalid/{endpoint}\\\""],
    target: { android: { cflags: ["/* not a comment */"], }, },
    srcs: ["runtime.cpp"],
}
''')
        self.assertEqual(self.errors(), [])

    def test_duplicate_source_module_definitions_are_rejected(self):
        definition = (self.top / self.source_file).read_text(encoding="utf-8")
        self.write(self.source_file, definition + definition)
        self.assert_failure("expected one definition")

    def test_prebuilt_in_expected_source_location_is_rejected(self):
        self.write(self.source_file, '''
cc_prebuilt_library_shared {
    name: "libcupid_runtime",
    srcs: ["proprietary/libcupid_runtime.so"],
}
''')
        self.assert_failure("expected cc_library_shared with source inputs")

    def test_disabled_source_module_is_rejected(self):
        self.write(self.source_file, '''
cc_library_shared {
    name: "libcupid_runtime",
    enabled: false,
    srcs: ["runtime.cpp"],
}
''')
        self.assert_failure("source definition is disabled")

    def test_missing_or_commented_source_list_is_rejected(self):
        self.write(self.source_file, '''
cc_library_shared {
    name: "libcupid_runtime",
    // srcs: ["runtime.cpp"],
    shared_libs: ["liblog"],
}
''')
        self.assert_failure("with source inputs")

    def test_empty_source_list_is_rejected(self):
        self.write(self.source_file, '''
cc_library_shared { name: "libcupid_runtime", srcs: [], }
''')
        self.assert_failure("with source inputs")

    def test_entire_blueprint_inside_a_block_comment_is_not_a_source_module(self):
        self.write(self.source_file, '''
/*
cc_library_shared {
    name: "libcupid_runtime",
    srcs: ["runtime.cpp"],
    target: {
        android: { cflags: ["-DANDROID"], },
    },
}
*/
''')
        self.assert_failure("expected one definition")

    def test_source_typed_module_cannot_hide_compiled_inputs_in_srcs(self):
        for binary in ("runtime.so", "runtime.a", "runtime.o", "runtime.bin", "RUNTIME.SO"):
            with self.subTest(binary=binary):
                self.write(self.source_file, '''
cc_library_shared {
    name: "libcupid_runtime",
    srcs: ["runtime.cpp", "%s"],
}
''' % binary)
                self.assert_failure("with source inputs")

    def test_vendor_prebuilt_shadow_is_rejected_even_with_prefer_false(self):
        self.write(self.vendor_file, '''
cc_prebuilt_library_shared {
    name: "libcupid_runtime",
    prefer: false,
    srcs: ["proprietary/libcupid_runtime.so"],
}
''')
        self.assert_failure("active prebuilt shadows source")

    def test_disabled_vendor_prebuilt_is_permitted(self):
        self.write(self.vendor_file, '''
cc_prebuilt_library_shared {
    name: "libcupid_runtime",
    enabled: false,
    srcs: ["proprietary/libcupid_runtime.so"],
}
''')
        self.assertEqual(self.errors(), [])

    def test_nested_disabled_property_does_not_hide_an_active_vendor_prebuilt(self):
        self.write(self.vendor_file, '''
cc_prebuilt_library_shared {
    name: "libcupid_runtime",
    target: { android_arm: { enabled: false, }, },
    srcs: ["proprietary/libcupid_runtime.so"],
}
''')
        self.assert_failure("active prebuilt shadows source")

    def test_missing_vendor_metadata_is_not_silently_skipped(self):
        (self.top / self.vendor_file).unlink()
        self.assert_failure("missing normalized vendor metadata")

    def test_commented_or_overridden_product_switch_cannot_pass(self):
        for text in (
            "# TARGET_USES_PREBUILT_RUNTIME := false\nPRODUCT_PACKAGES += libcupid_runtime\n",
            "TARGET_USES_PREBUILT_RUNTIME := false\n"
            "TARGET_USES_PREBUILT_RUNTIME := true\nPRODUCT_PACKAGES += libcupid_runtime\n",
        ):
            with self.subTest(text=text):
                self.write(self.device_file, text)
                self.assert_failure("requires TARGET_USES_PREBUILT_RUNTIME := false")

    def test_make_source_service_uses_its_own_clear_vars_block(self):
        contract = copy.deepcopy(self.contract)
        module = contract["source_built"][0]["modules"][0]
        module.update(file="Android.mk", type="BUILD_EXECUTABLE")
        self.write(self.root + "/Android.mk", '''
LOCAL_PATH := $(call my-dir)
include $(CLEAR_VARS)
LOCAL_MODULE := unrelated_library
LOCAL_SRC_FILES := unrelated.cpp
include $(BUILD_SHARED_LIBRARY)
include $(CLEAR_VARS)
LOCAL_MODULE := libcupid_runtime
LOCAL_SRC_FILES := \\
    service.cpp \\
    runtime.cpp
include $(BUILD_EXECUTABLE)
''')
        self.assertEqual(self.errors(contract=contract), [])

    def test_make_prebuilt_service_cannot_inherit_source_from_an_earlier_module(self):
        contract = copy.deepcopy(self.contract)
        module = contract["source_built"][0]["modules"][0]
        module.update(file="Android.mk", type="BUILD_EXECUTABLE")
        self.write(self.root + "/Android.mk", '''
include $(CLEAR_VARS)
LOCAL_MODULE := unrelated_library
LOCAL_SRC_FILES := unrelated.cpp
include $(BUILD_SHARED_LIBRARY)
include $(CLEAR_VARS)
LOCAL_MODULE := libcupid_runtime
LOCAL_SRC_FILES := proprietary/runtime
include $(BUILD_PREBUILT)
''')
        self.assert_failure("expected BUILD_EXECUTABLE with source inputs", contract=contract)

    def test_empty_make_source_assignment_cannot_consume_the_next_variable(self):
        contract = copy.deepcopy(self.contract)
        module = contract["source_built"][0]["modules"][0]
        module.update(file="Android.mk", type="BUILD_EXECUTABLE")
        self.write(self.root + "/Android.mk", '''
include $(CLEAR_VARS)
LOCAL_MODULE := libcupid_runtime
LOCAL_SRC_FILES :=
LOCAL_SHARED_LIBRARIES := liblog
include $(BUILD_EXECUTABLE)
''')
        self.assert_failure("with source inputs", contract=contract)

    def test_generated_module_info_accepts_source_owner_and_installed_output(self):
        info = {"libcupid_runtime": {
            "path": [self.root + "/service"],
            "installed": ["out/target/product/cupid/vendor/lib64/libcupid_runtime.so"],
        }}
        self.assertEqual(self.errors(info), [])

    def test_generated_module_info_rejects_a_vendor_owner(self):
        info = {"libcupid_runtime": {
            "path": ["vendor/xiaomi/test"],
            "installed": ["out/target/product/cupid/vendor/lib64/libcupid_runtime.so"],
        }}
        self.assert_failure("unexpected owner", info)

    def test_generated_module_info_requires_exact_directory_boundary(self):
        info = {"libcupid_runtime": {
            "path": [self.root + "-prebuilt"],
            "installed": ["out/target/product/cupid/vendor/lib64/libcupid_runtime.so"],
        }}
        self.assert_failure("unexpected owner", info)

    def test_generated_module_info_rejects_missing_runtime_output(self):
        self.assert_failure("no installed output", {"libcupid_runtime": {
            "path": [self.root], "installed": [],
        }})

    def test_generated_module_info_rejects_missing_module(self):
        self.assert_failure("absent from the generated graph", {})

    def test_header_dependency_does_not_need_an_installed_binary(self):
        contract = copy.deepcopy(self.contract)
        module = contract["source_built"][0]["modules"][0]
        module.update(type="cc_library_headers", installed=False)
        self.write(self.source_file, '''
cc_library_headers { name: "libcupid_runtime", export_include_dirs: ["include"], }
''')
        info = {"libcupid_runtime": {"path": [self.root], "installed": []}}
        self.assertEqual(self.errors(info, contract), [])

    def test_source_filegroup_skips_graph_output_but_still_requires_its_definition(self):
        contract = copy.deepcopy(self.contract)
        module = contract["source_built"][0]["modules"][0]
        module.update(type="filegroup", installed=False, graph_module=False)
        self.write(self.source_file, '''
filegroup {
    name: "libcupid_runtime",
    srcs: ["runtime.cpp"],
    visibility: ["//device/xiaomi/cupid"],
}
''')
        self.assertEqual(self.errors({}, contract), [])
        self.write(self.source_file, "// source filegroup was accidentally removed\n")
        self.assert_failure("expected one definition", {}, contract)


if __name__ == "__main__":
    unittest.main()
