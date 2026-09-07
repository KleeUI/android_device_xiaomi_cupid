# Klee Cupid device-tree inputs

This directory is the source input for the Cupid Waipio kernel build.  The
manifest links it to `kernel_platform/msm-kernel/arch/arm64/boot/dts/vendor`
so `dtbs` and `dtbo.img` are produced by Kbuild during `klee_build`.

The Qualcomm Waipio base descriptions and their device-tree bindings are
licensed source inputs.  Klee-specific integration is limited to the Cupid
board, PMIC, camera, audio, and display descriptions and to the Kbuild target
selection.  No generated `dtb`, `dtbo`, `dtb.img`, or `dtbo.img` is checked in,
and no Xiaomi stock DT image is accepted by the board configuration.

The board configuration deliberately fails when this directory is absent.
That keeps a missing manifest link from silently creating an empty or stale
boot device tree.
