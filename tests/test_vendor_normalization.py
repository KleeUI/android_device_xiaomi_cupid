"""Exercise patch migration and fail-closed preflight with public fixtures."""

import difflib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import klee_vendor  # noqa: E402


GNU_PATCH = shutil.which("patch")
if GNU_PATCH is None:
    git_patch = Path(r"C:\Program Files\Git\usr\bin\patch.exe")
    if git_patch.is_file():
        GNU_PATCH = str(git_patch)


@unittest.skipUnless(GNU_PATCH, "GNU patch is required for patch round-trip tests")
class VendorNormalizationTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.top = Path(self.directory.name) / "top"
        self.device = Path(self.directory.name) / "device"
        (self.device / "patches").mkdir(parents=True)
        self.metadata = "vendor/xiaomi/cupid/Android.bp"
        self.source = "vendor/qcom/opensource/libvmmem/vmmem.cpp"
        self.before = 'soong_namespace {}\n// baseline\n' + '// stable context\n' * 5
        self.first = self.before.replace("baseline", "first")
        self.final = self.before.replace("baseline", "normalized")
        self.source_before = 'LOG("%lu", (entries.size()));\n'
        self.source_after = 'LOG("%zu", entries.size());\n'
        for relative in klee_vendor.REQUIRED_VENDOR_FILES:
            self.write(relative, self.before if relative == self.metadata else "// fixture\n")
        self.write(self.source, self.source_before)
        self.make_patch("0001-first.patch", self.metadata, self.before, self.first)
        self.make_patch("0002-last.patch", self.metadata, self.first, self.final)
        self.make_patch("0015-source.patch", self.source, self.source_before, self.source_after)
        self.addCleanup(patch.stopall)
        patch.object(klee_vendor, "PATCH_NAMES", ("0001-first.patch", "0002-last.patch")).start()
        patch.object(klee_vendor, "SOURCE_PATCH_NAMES", ("0015-source.patch",)).start()
        patch.dict(os.environ, {"PATH": str(Path(GNU_PATCH).parent) + os.pathsep + os.environ.get("PATH", "")}).start()

    def write(self, relative, content):
        target = self.top / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)

    def make_patch(self, name, relative, before, after):
        text = "".join(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True),
            fromfile="a/" + relative, tofile="b/" + relative,
        ))
        with (self.device / "patches" / name).open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)

    def snapshot(self):
        return {str(p.relative_to(self.top)): p.read_bytes() for p in self.top.rglob("*") if p.is_file()}

    def apply(self, **kwargs):
        return dict(klee_vendor.apply_vendor_patches(self.top, self.device, **kwargs))

    def test_check_only_does_not_modify_pristine_inputs(self):
        before = self.snapshot()
        result = self.apply(check_only=True)
        self.assertEqual(result["0001-first.patch"], "pending")
        self.assertEqual(result["0002-last.patch"], "pending")
        self.assertEqual(result["0015-source.patch"], "pending")
        self.assertEqual(self.snapshot(), before)

    def test_apply_and_repeat_are_byte_identical(self):
        self.apply()
        self.assertEqual((self.top / self.metadata).read_text(), self.final)
        self.assertEqual((self.top / self.source).read_text(), self.source_after)
        before = self.snapshot()
        result = self.apply()
        self.assertEqual(result["0001-first.patch"], "already-applied")
        self.assertEqual(result["0015-source.patch"], "already-applied")
        self.assertEqual(self.snapshot(), before)

    def test_previous_prefix_and_existing_source_fix_upgrade_once(self):
        self.write(self.metadata, self.first)
        self.write(self.source, self.source_after)
        before = self.snapshot()
        result = self.apply(check_only=True)
        self.assertEqual(result["0001-first.patch"], "already-applied")
        self.assertEqual(result["0002-last.patch"], "pending")
        self.assertEqual(result["0015-source.patch"], "already-applied")
        self.assertEqual(self.snapshot(), before)
        self.apply()
        self.assertEqual((self.top / self.metadata).read_text(), self.final)
        self.assertEqual((self.top / self.source).read_text(), self.source_after)

    def test_equivalent_historical_prefixes_can_resume(self):
        self.make_patch("0003-revert.patch", self.metadata, self.final, self.first)
        self.make_patch("0004-finish.patch", self.metadata, self.first, self.final)
        with patch.object(klee_vendor, "PATCH_NAMES", (
            "0001-first.patch", "0002-last.patch", "0003-revert.patch", "0004-finish.patch",
        )):
            self.write(self.metadata, self.first)
            result = self.apply()
            self.assertEqual(result["0003-revert.patch"], "already-applied")
            self.assertEqual(result["0004-finish.patch"], "applied")
        self.assertEqual((self.top / self.metadata).read_text(), self.final)

    def test_unrelated_generated_metadata_is_preserved(self):
        extra = '\n// unrelated generated module\n'
        self.write(self.metadata, self.before + extra)
        self.apply()
        self.assertEqual((self.top / self.metadata).read_text(), self.final + extra)

    def test_source_drift_is_rejected_before_metadata_is_changed(self):
        self.write(self.source, 'LOG("drift");\n')
        before = self.snapshot()
        with self.assertRaisesRegex(klee_vendor.VendorPreparationError, "source compatibility patch"):
            self.apply()
        self.assertEqual(self.snapshot(), before)

    def test_missing_source_is_rejected_before_metadata_is_changed(self):
        (self.top / self.source).unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(klee_vendor.VendorPreparationError, "source compatibility patch"):
            self.apply()
        self.assertEqual(self.snapshot(), before)

    def test_metadata_drift_is_rejected_before_source_is_changed(self):
        self.write(self.metadata, "// unknown metadata\n")
        before = self.snapshot()
        with self.assertRaisesRegex(klee_vendor.VendorPreparationError, "vendor patch stack"):
            self.apply()
        self.assertEqual(self.snapshot(), before)

    def test_audio_filegroup_drift_is_rejected_before_any_patch_is_written(self):
        self.write(self.metadata, self.before + 'filegroup { name: "cupid_audioadsprpcd_blob" }\n')
        before = self.snapshot()
        with self.assertRaisesRegex(klee_vendor.VendorPreparationError, "audio filegroup"):
            self.apply()
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
