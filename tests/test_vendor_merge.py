"""Exercise merging prepared vendor inputs and protecting published files."""

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import klee_vendor_merge as merge  # noqa: E402
from tools.klee_vendor import VendorPreparationError  # noqa: E402


class VendorMergeTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name).resolve()
        self.prepared = root / "prepared"
        self.top = root / "android"
        self.device = root / "device"
        self.cupid = self.prepared / merge.CUPID
        self.common = self.prepared / merge.COMMON
        self.destination = self.top / merge.CUPID

        self.write(self.cupid / "proprietary/vendor/firmware/gpu.bin", b"gpu")
        self.write(self.common / "proprietary/vendor/firmware/gpu.bin", b"gpu")
        self.write(self.common / "proprietary/system/framework/WfdCommon.jar", b"jar")
        self.write(self.common / "compat/c2audio-service/service.cpp", b"source")
        self.write(self.common / "compat/c2audio-service/qc2_factory_abi.h", b"header")
        self.write(self.cupid / "Android.bp", b'''soong_namespace {
    imports: ["vendor/xiaomi/sm8450-common"],
}
prebuilt_etc {
    name: "gpu_firmware",
    src: "proprietary/vendor/firmware/gpu.bin",
}
''')
        self.write(self.common / "Android.bp", b'''soong_namespace {}
cc_binary {
    name: "vendor.qti.media.c2audio@1.0-service",
    srcs: ["compat/c2audio-service/service.cpp"],
}
''')
        for tree, owner, fragment in ((self.cupid, merge.CUPID, "cupid-vendor.mk"),
                                      (self.common, merge.COMMON, "sm8450-common-vendor.mk")):
            self.write(tree / fragment, f'''PRODUCT_SOONG_NAMESPACES += \\
    {owner}

PRODUCT_COPY_FILES += \\
    {owner}/proprietary/vendor/firmware/gpu.bin:$(TARGET_COPY_OUT_VENDOR)/firmware/gpu.bin \\
    {owner}/proprietary/vendor/firmware/gpu.bin:$(TARGET_COPY_OUT_VENDOR)/firmware/{tree.name}.bin
'''.encode("ascii"))

    @staticmethod
    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def run_merge(self):
        return merge.merge_vendor_inputs(self.top, self.prepared, self.device)

    def test_merge_and_repeat(self):
        original_cupid = merge._inventory(self.cupid)
        original_common = merge._inventory(self.common)
        self.assertEqual(self.run_merge(), [(merge.CUPID, "updated")])
        blueprint = (self.destination / "Android.bp").read_text()
        self.assertEqual(blueprint.count("soong_namespace"), 1)
        for token in ("vendor/qcom/opensource/agm", "vendor/qcom/opensource/pal",
                      "cupid_wfd_common_jar", "gpu_firmware", "vendor.qti.media.c2audio@1.0-service"):
            self.assertEqual(blueprint.count(token), 1)
        self.assertIn('visibility: ["//device/xiaomi/cupid:__pkg__"]', blueprint)
        self.assertNotIn(merge.COMMON, blueprint)
        common_mk = (self.destination / "sm8450-common-vendor.mk").read_text()
        cupid_mk = (self.destination / "cupid-vendor.mk").read_text()
        self.assertIn("PRODUCT_SOONG_NAMESPACES", common_mk)
        self.assertNotIn("PRODUCT_SOONG_NAMESPACES", cupid_mk)
        self.assertNotIn(merge.COMMON, common_mk)
        self.assertIn("/firmware/gpu.bin:$(TARGET_COPY_OUT_VENDOR)/firmware/gpu.bin", common_mk)
        self.assertNotIn("/firmware/gpu.bin:$(TARGET_COPY_OUT_VENDOR)/firmware/gpu.bin", cupid_mk)
        self.assertIn("/firmware/cupid.bin", cupid_mk)
        self.assertEqual((self.destination / "compat/c2audio-service/qc2_factory_abi.h").read_bytes(), b"header")
        self.assertEqual(merge.check_merged_vendor(self.top), [(merge.CUPID, "merged")])
        self.assertEqual(self.run_merge(), [(merge.CUPID, "unchanged")])
        self.assertEqual(merge._inventory(self.cupid), original_cupid)
        self.assertEqual(merge._inventory(self.common), original_common)

    def test_preserves_symlink_and_mode(self):
        original = self.common / "proprietary/vendor/firmware/real.bin"
        self.write(original, b"firmware")
        original.chmod(0o750)
        link = original.with_name("alias.bin")
        try:
            link.symlink_to("real.bin")
        except OSError:
            self.skipTest("Symlink creation is unavailable")
        self.run_merge()
        output = self.destination / "proprietary/vendor/firmware"
        self.assertEqual(os.readlink(output / "alias.bin"), "real.bin")
        self.assertEqual((output / "real.bin").stat().st_mode, original.stat().st_mode)

    def test_collision_and_missing_required_file_leave_destination_absent(self):
        overlap = self.common / "proprietary/vendor/firmware/gpu.bin"
        overlap.write_bytes(b"different")
        with self.assertRaisesRegex(VendorPreparationError, "Vendor input collision"):
            self.run_merge()
        self.assertFalse(self.destination.exists())

        overlap.write_bytes(b"gpu")
        (self.common / "compat/c2audio-service/service.cpp").unlink()
        with self.assertRaisesRegex(VendorPreparationError, "Missing required vendor input"):
            self.run_merge()
        self.assertFalse(self.destination.exists())

    def test_rejects_duplicate_modules(self):
        path = self.cupid / "Android.bp"
        path.write_text(path.read_text().replace('name: "gpu_firmware"', 'name: "vendor.qti.media.c2audio@1.0-service"'))
        with self.assertRaisesRegex(VendorPreparationError, "Duplicate Soong module"):
            self.run_merge()

    def test_rejects_prebuilt_audio_launcher(self):
        path = self.common / "Android.bp"
        path.write_text(path.read_text().replace('cc_binary', 'cc_prebuilt_binary'))
        with self.assertRaisesRegex(VendorPreparationError, "source C2 audio launcher"):
            self.run_merge()

    def test_preserves_existing_unowned_or_edited_destination(self):
        self.write(self.destination / "keep", b"local")
        with self.assertRaisesRegex(VendorPreparationError, "Preserve the existing vendor tree"):
            self.run_merge()
        self.assertEqual((self.destination / "keep").read_bytes(), b"local")
        (self.destination / "keep").unlink()
        self.destination.rmdir()

        self.run_merge()
        generated = self.destination / "Android.bp"
        generated.write_text("local edit")
        with self.assertRaisesRegex(VendorPreparationError, "metadata has changed"):
            merge.check_merged_vendor(self.top)
        with self.assertRaisesRegex(VendorPreparationError, "have been edited"):
            self.run_merge()
        self.assertEqual(generated.read_text(), "local edit")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Atomic directory exchange requires Linux")
    def test_replaces_owned_output_atomically(self):
        self.run_merge()
        self.write(self.common / "compat/c2audio-service/service.cpp", b"updated source")
        with patch.object(merge, "_publish_tree", side_effect=OSError("publication error")):
            with self.assertRaisesRegex(OSError, "publication error"):
                self.run_merge()
        self.assertEqual((self.destination / "compat/c2audio-service/service.cpp").read_bytes(), b"source")
        self.assertEqual(self.run_merge(), [(merge.CUPID, "updated")])
        self.assertEqual((self.destination / "compat/c2audio-service/service.cpp").read_bytes(), b"updated source")

    def test_rejects_active_separate_common_tree(self):
        (self.top / merge.COMMON).mkdir(parents=True)
        with self.assertRaisesRegex(VendorPreparationError, "separate vendor tree still exists"):
            self.run_merge()


if __name__ == "__main__":
    unittest.main()
