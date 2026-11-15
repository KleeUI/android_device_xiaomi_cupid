# R6 Post-Flash Validation (2026-11-15)

This report records a scoped post-flash check on Xiaomi Cupid. It is a smoke-test record, not a full hardware qualification or a binary release. Device identifiers, network names and addresses, local paths, raw logs, screenshots, write scripts, and tokens are intentionally omitted.

## Result

- The full input-image byte ranges of A-slot `system`, `system_ext`, `product`, and `vbmeta_system` were read back. Each readback SHA-256 matched its input image; the remaining `vbmeta_system` partition tail was preserved.
- Pre/post hashes for protected partitions, the non-target portion of `super`, and the sampled `userdata` prefix matched. The B slot and other protected areas were not modified.
- The installed root vbmeta signature, the `vbmeta_system` signature and chained public key, and the three complete image hashtrees passed offline verification. The installed root vbmeta flags were `3` (verification and hashtree enforcement disabled), so this does not demonstrate enforced AVB on the device. This audit did not verify FEC regeneration, device rollback-index storage, other root descriptors, or the recovery chain.
- One cache-flush command was issued with multiple paths and returned an argument-count error. The paths were flushed individually afterward, then the full target readback verification passed.
- The device booted from slot A: `boot_completed=1`, SELinux was enforcing, and `system_server` had one start in the captured boot.

## Hardware Smoke Checks

- Wi-Fi scan requests succeeded and returned results during the test. Wi-Fi was disabled in the final snapshot; association and internet access were not verified.
- Bluetooth was on and discovery found 16 devices. No devices were paired, and connection/profile throughput was not tested.
- The NFC service reported on. No tag interaction was tested.
- Front and rear camera preview pipelines started. No still image was taken, and the camera was closed after the check.
- The captured `system_server` crash tag had no entries. The device also had older tombstones, so this does not establish that the device was free of all crashes.

## Image and Evidence Digests

SHA-256 values identify the tested inputs and local audit artifacts without publishing the images or raw device records.

| Artifact | SHA-256 |
| --- | --- |
| `system` image | `4a1d5546b29c3b4d68875eec7df0a1648cdf12f608487731ad7e060b16686635` |
| `system_ext` image | `d15e981e765161198d82455308bc32be8931169fda9a94dfa6ea80a2648c3a27` |
| `product` image | `704dbd929d3ead411581a7577e002d44e69f8f6f838cd605333d20931cc5e20f` |
| `vbmeta_system` image | `8a4057b22b7216008bf4f8da414880c025e8065816b4cd1ecd367b8cdc657601` |
| Build manifest | `7c1a0409c44d3d4cd69ea63a7b65c1bde57a06609de6ec77f8bc3e581f86dbd4` |
| Flash plan | `45c6aacc1811c388b862edee76fbb4eb8e51ef369aa8ea9a4733ed1bc171cc36` |
| AVB audit report | `7700831f286e4317eeb105c7822016d3c8f28730825290b74921a05a86cb84ae` |
| Image writer | `4e8aa19a46f75c0ffa850bceeb859c9717c38a7d4dad6410de282aeda3d09e3c` |
| Readback verifier | `195a9643da019ff8b61233c76d20cfc5a39ddb12b789213db969d1128dc4bf77` |
| AVB audit tool | `e977460cc48b5b08f73482c2670901938b5715234760348d0cbdfee0a5e3469a` |

## Related Source Fixes

The related display compatibility fixes are already present on the `Klee-1.0` branches under the `herobrinejjjj` account:

- `android_device_xiaomi_cupid`: `a130aad34de9a308c477a54370dec68951df5a43` adds the product property that disables incompatible proprietary SDM plugins. `Change-Id: Ib16c924be2e55430ab170ee5e97eb681578dedd1`.
- `android_hardware_qcom_display`: `5bf8dc4287874e8ffc881e1c44a4b8fa2a5f2666` (`I760ec05fb28b3792f6b0c17983cb375c7f16df94`) gates incompatible plugin loading; `137dfca8e634bc0bf6ac571c7d23d55572bfb720` (`Ic5f6ab18b8448a692bb9375d2aa28a17f151a9e6`) preserves platform resource extensions; `19298cb6fbce6304f53e296795e664ed094ba51a` (`Ib26791d6a8051b4019b96b458722a6c5ab532c94`) restores the built-in resource fallback.

Raw device logs and command ledgers remain local because they contain device, network, and host details. This report deliberately omits them and does not claim full functional qualification.
