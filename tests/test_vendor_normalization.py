"""Exercise patch migration and fail-closed preflight with public fixtures."""

import difflib
import os
from pathlib import Path
import shutil
import stat
import subprocess
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


# Public build recipe only. The vendor implementation is deliberately not a
# test fixture; production checks require both existing source inputs.
C2AUDIO_SOURCE_R6 = '''cc_binary {
    name: "vendor.qti.media.c2audio@1.0-service",
    owner: "xiaomi",
    defaults: ["libcodec2-hidl-defaults@1.0"],
    srcs: ["compat/c2audio-service/service.cpp"],
    relative_install_path: "hw",
    soc_specific: true,
    compile_multilib: "64",
    cpp_std: "gnu++20",
    cflags: [
        "-Wall", "-Wextra", "-Werror",
        "-O1",
        "-fvisibility=default",
        "-fno-exceptions", "-fno-rtti",
        "-mbranch-protection=standard", "-fstack-protector-strong",
        "-Wno-error=deprecated-declarations",
        // Current public Codec2 headers specialize these libc++ traits and use
        // enum combinations deprecated by the tree's Clang 22 toolchain.
        "-Wno-invalid-specialization",
        "-Wno-deprecated-copy",
        "-Wno-deprecated-enum-enum-conversion",
        "-Wno-deprecated-anon-enum-enum-conversion",
    ],
    sanitize: { cfi: true },
    lto: { thin: true },
    shared_libs: [
        "android.hardware.media.c2@1.0",
        "libavservices_minijail",
        "libbinder",
        "libcodec2_hidl@1.0",
        "libcodec2_vndk",
        "libhidlbase",
        "liblog",
        "libutils",
        "libdl",
        "libqc2audio_base",
        "libqc2audio_utils",
        "libqc2audio_basecodec",
        "libqc2audio_platform",
        "libqc2audio_core",
        "libqdMetaData",
    ],
}
'''


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

    def install_c2audio_overlay(self, newline=b"\n"):
        relative = klee_vendor._C2AUDIO_METADATA
        prefix, suffix = b"// preserve spacing  \n\n", b"\n// common baseline\n"
        baseline = prefix + klee_vendor._C2AUDIO_PREBUILT + suffix
        final = baseline.replace(b"common baseline", b"common normalized")
        self.make_patch("0003-common.patch", relative, baseline.decode(), final.decode())
        patch.object(klee_vendor, "PATCH_NAMES", (
            "0001-first.patch", "0002-last.patch", "0003-common.patch",
        )).start()
        overlay = C2AUDIO_SOURCE_R6.encode().replace(b"\n", newline)
        (self.top / relative).write_bytes(prefix + overlay + suffix)
        for path in klee_vendor._C2AUDIO_SOURCE_FILES:
            self.write(path, "// existing source input fixture\n")
        return overlay, prefix + overlay + suffix.replace(b"baseline", b"normalized")

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

    def test_c2audio_source_overlay_upgrades_pristine_and_prefix_and_preserves_bytes(self):
        for newline in (b"\n", b"\r\n"):
            for initial in (self.before, self.first, self.final):
                with self.subTest(newline=newline, initial=initial):
                    self.write(self.metadata, initial)
                    self.write(self.source, self.source_before)
                    overlay, expected = self.install_c2audio_overlay(newline)
                    before = self.snapshot()
                    result = self.apply(check_only=True)
                    self.assertEqual(result["0003-common.patch"], "pending")
                    self.assertEqual(self.snapshot(), before)
                    result = self.apply()
                    self.assertEqual(result["0003-common.patch"], "applied")
                    common = self.top / klee_vendor._C2AUDIO_METADATA
                    self.assertEqual(common.read_bytes(), expected)
                    self.assertEqual(klee_vendor._c2audio_source_overlay(common.read_bytes()), overlay)
                    self.assertEqual((self.top / self.metadata).read_text(), self.final)
                    self.assertEqual((self.top / self.source).read_text(), self.source_after)
                    after = self.snapshot()
                    self.assertEqual(self.apply()["0003-common.patch"], "already-applied")
                    self.apply(check_only=True)
                    self.assertEqual(self.snapshot(), after)

    def test_unknown_or_duplicate_c2audio_overlay_fails_before_any_writes(self):
        for change in ("flags", "name-spacing", "renamed", "duplicate", "renamed-duplicate", "mixed-newline"):
            with self.subTest(change=change):
                overlay, _ = self.install_c2audio_overlay()
                common = self.top / klee_vendor._C2AUDIO_METADATA
                raw = common.read_bytes()
                if change == "flags":
                    raw = raw.replace(b'cpp_std: "gnu++20"', b'cpp_std: "gnu++23"')
                elif change == "name-spacing":
                    raw = raw.replace(b'name: "vendor.qti.media.c2audio', b'name : "vendor.qti.media.c2audio')
                elif change == "renamed":
                    raw = raw.replace(b'name: "vendor.qti.media.c2audio', b'name: "changed.vendor.qti.media.c2audio')
                elif change == "duplicate":
                    raw += overlay
                elif change == "renamed-duplicate":
                    raw += overlay.replace(b'name: "vendor.qti.media.c2audio', b'name: "changed.vendor.qti.media.c2audio')
                else:
                    raw = raw.replace(b"cc_binary {\n", b"cc_binary {\r\n")
                common.write_bytes(raw)
                before = self.snapshot()
                with self.assertRaisesRegex(klee_vendor.VendorPreparationError, "C2 audio"):
                    self.apply()
                self.assertEqual(self.snapshot(), before)

    def test_c2audio_overlay_requires_both_nonempty_source_inputs(self):
        for relative in klee_vendor._C2AUDIO_SOURCE_FILES:
            for empty in (False, True):
                with self.subTest(relative=relative, empty=empty):
                    self.install_c2audio_overlay()
                    target = self.top / relative
                    if empty:
                        target.write_bytes(b"")
                    else:
                        target.unlink()
                    before = self.snapshot()
                    with self.assertRaisesRegex(klee_vendor.VendorPreparationError, "missing its source inputs"):
                        self.apply()
                    self.assertEqual(self.snapshot(), before)

    def test_c2audio_overlay_does_not_bypass_other_metadata_drift(self):
        self.install_c2audio_overlay()
        common = self.top / klee_vendor._C2AUDIO_METADATA
        common.write_bytes(common.read_bytes().replace(b"common baseline", b"common unknown"))
        before = self.snapshot()
        with self.assertRaisesRegex(klee_vendor.VendorPreparationError, "vendor patch stack"):
            self.apply()
        self.assertEqual(self.snapshot(), before)

    def test_c2audio_overlay_does_not_bypass_source_compatibility_drift(self):
        self.install_c2audio_overlay()
        self.write(self.source, "// unknown source compatibility state\n")
        before = self.snapshot()
        with self.assertRaisesRegex(klee_vendor.VendorPreparationError, "source compatibility patch"):
            self.apply()
        self.assertEqual(self.snapshot(), before)

    def test_c2audio_overlay_staging_failure_does_not_write_real_inputs(self):
        self.install_c2audio_overlay()
        before = self.snapshot()
        apply_patch = klee_vendor._apply_patch

        def fail_staged_write(top, patch_file, *, reverse):
            if top.name.startswith("klee-vendor-c2audio-"):
                return subprocess.CompletedProcess([], 1, "injected staged patch failure")
            return apply_patch(top, patch_file, reverse=reverse)

        with patch.object(klee_vendor, "_apply_patch", side_effect=fail_staged_write):
            with self.assertRaisesRegex(klee_vendor.VendorPreparationError, "injected staged patch failure"):
                self.apply()
        self.assertEqual(self.snapshot(), before)

    def test_c2audio_overlay_equal_length_source_fix_updates_mtime_and_keeps_mode(self):
        self.install_c2audio_overlay()
        # Use the real vmmem diagnostic context but isolate the equal-length
        # format correction; the production patch also removes parentheses.
        source_before = (
            '    if (vmperms.size() > nr_acl_entries) {\n'
            '        LOG(PRI_ERROR, "Invalid number of acl_entries %lu", vmperms.size());\n'
            '        return -EINVAL;\n'
            '    }\n'
        )
        source_after = source_before.replace("%lu", "%zu")
        self.assertEqual(len(source_before.encode()), len(source_after.encode()))
        self.write(self.source, source_before)
        self.make_patch("0015-source.patch", self.source, source_before, source_after)
        source = self.top / self.source
        source.chmod(0o640)
        old_ns = 1_000_000_000_000_000_000
        os.utime(source, ns=(old_ns, old_ns))
        original = source.stat()
        expected_mode = stat.S_IMODE(original.st_mode)
        before = self.snapshot()
        self.apply(check_only=True)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(source.stat().st_mtime_ns, original.st_mtime_ns)
        self.apply()
        current = source.stat()
        self.assertEqual(source.read_bytes(), source_after.encode())
        self.assertEqual(current.st_size, original.st_size)
        self.assertGreater(current.st_mtime_ns, original.st_mtime_ns)
        self.assertEqual(stat.S_IMODE(current.st_mode), expected_mode)
        self.apply()
        self.apply(check_only=True)
        self.assertEqual(source.stat().st_mtime_ns, current.st_mtime_ns)
        self.assertEqual(stat.S_IMODE(source.stat().st_mode), expected_mode)


if __name__ == "__main__":
    unittest.main()
