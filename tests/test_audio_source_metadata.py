"""Regression coverage for removing the obsolete audio wrapper blob reference."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.klee_vendor import (  # noqa: E402
    VendorPreparationError,
    _normalize_audio_filegroup,
)


LEGACY_GROUP = '''filegroup {
    name: "cupid_audioadsprpcd_blob",
    srcs: ["proprietary/vendor/bin/audioadsprpcd"],
    visibility: ["//device/xiaomi/cupid"],
}
'''


class AudioSourceMetadataTest(unittest.TestCase):
    def test_fresh_metadata_needs_no_wrapper_blob(self):
        with tempfile.TemporaryDirectory() as directory:
            top = Path(directory)
            generated = top / "vendor/xiaomi/cupid/Android.bp"
            generated.parent.mkdir(parents=True)
            generated.write_text("soong_namespace {}\n", encoding="utf-8")
            self.assertEqual(
                _normalize_audio_filegroup(top, check_only=False)[1], "already-absent"
            )
            self.assertEqual(generated.read_text(), "soong_namespace {}\n")

    def test_old_reference_is_removed_without_deleting_private_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            top = Path(directory)
            vendor = top / "vendor/xiaomi/cupid"
            vendor.mkdir(parents=True)
            generated = vendor / "Android.bp"
            original = "soong_namespace {}\n\n" + LEGACY_GROUP
            generated.write_text(original, encoding="utf-8")
            listener = vendor / "proprietary/vendor/lib64/libadsp_default_listener.so"
            listener.parent.mkdir(parents=True)
            listener.write_bytes(b"private listener stays")
            self.assertEqual(
                _normalize_audio_filegroup(top, check_only=True)[1], "pending-removal"
            )
            self.assertEqual(generated.read_text(), original)
            self.assertEqual(
                _normalize_audio_filegroup(top, check_only=False)[1], "removed"
            )
            self.assertEqual(generated.read_text(), "soong_namespace {}\n\n")
            self.assertEqual(listener.read_bytes(), b"private listener stays")
            self.assertEqual(
                _normalize_audio_filegroup(top, check_only=False)[1], "already-absent"
            )

    def test_modified_reference_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            top = Path(directory)
            generated = top / "vendor/xiaomi/cupid/Android.bp"
            generated.parent.mkdir(parents=True)
            original = LEGACY_GROUP.replace("vendor/bin/audioadsprpcd", "vendor/bin/custom")
            generated.write_text(original, encoding="utf-8")
            with self.assertRaises(VendorPreparationError):
                _normalize_audio_filegroup(top, check_only=False)
            self.assertEqual(generated.read_text(), original)

    def test_removal_preserves_other_bytes_for_lf_and_crlf_inputs(self):
        for newline in (b"\n", b"\r\n"):
            with self.subTest(newline=newline), tempfile.TemporaryDirectory() as directory:
                top = Path(directory)
                generated = top / "vendor/xiaomi/cupid/Android.bp"
                generated.parent.mkdir(parents=True)
                before = b"// keep spacing  " + newline + newline
                after = newline + b"// preserve trailing blank lines" + newline * 3
                block = LEGACY_GROUP.encode("utf-8").replace(b"\n", newline)
                generated.write_bytes(before + block + after)
                self.assertEqual(_normalize_audio_filegroup(top, check_only=False)[1], "removed")
                self.assertEqual(generated.read_bytes(), before + after)
                self.assertEqual(_normalize_audio_filegroup(top, check_only=False)[1], "already-absent")

    def test_noncanonical_module_name_spacing_is_rejected_as_drift(self):
        for name_field in (
            'name:"cupid_audioadsprpcd_blob"',
            'name : "cupid_audioadsprpcd_blob"',
        ):
            with self.subTest(name_field=name_field), tempfile.TemporaryDirectory() as directory:
                top = Path(directory)
                generated = top / "vendor/xiaomi/cupid/Android.bp"
                generated.parent.mkdir(parents=True)
                original = LEGACY_GROUP.replace('name: "cupid_audioadsprpcd_blob"', name_field)
                generated.write_text(original, encoding="utf-8")
                with self.assertRaisesRegex(VendorPreparationError, "audio filegroup"):
                    _normalize_audio_filegroup(top, check_only=True)
                self.assertEqual(generated.read_text(), original)


if __name__ == "__main__":
    unittest.main()
