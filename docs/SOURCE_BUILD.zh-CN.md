# Cupid 源码构建范围

本项目的目标是：有完整且与 Cupid 接口相匹配的源码时，从源码构建，并阻止同名
vendor 预编译模块重新覆盖它。该目标不意味着硬件固件、校准数据和未公开实现可以
自动变成源码，也不意味着静态配置通过后所有硬件功能已经验收。

## 本轮实际调整

- 把 AudioReach graphservices、utils 和 location 指向包含 Klee 适配的固定源码版本，
  使公开同步结果包含服务器曾使用的 Soong 模块和 Make 重复定义保护。
- 补齐 `libvmmem` 的源码清单入口及格式检查修复，避免依靠构建服务器额外注入文件。
- 规范化 GNSS 元数据时禁用同名 `libgnsspps` 预编译覆盖，保留源码库的模块所有权。
- 将 `cupid_audioadsprpcd` 的启动包装器改为源码模块；继续调用匹配的私有 listener，
  保留设备 rc 的启动参数与已有启动行为。这不替换整个 FastRPC 栈。
- 增加源码构建合同与产品解析门禁，检查模块定义、类型、产品开关和 vendor 覆盖。
  它还可以使用本次构建的 `module-info.json` 核对实际模块所属目录及安装产物。

## 各子系统的边界

| 子系统 | 源码构建部分 | 仍需区分的部分 |
| --- | --- | --- |
| 内核、DTB/DTBO、DLKM | 由设备的 kernel 构建适配及固定 Qualcomm/MiCode 源码生成 | `source-module-gaps.json` 中列出的缺失驱动不因门禁通过而补齐；禁止用不匹配库存 `.ko` 补位 |
| 音频 HAL | `audiohalservice.qti`、core/effects HAL、AGM、PAL | 私有 codec/effect 扩展、DSP 固件及 ACDB 校准仍有独立依赖 |
| AudioReach 低层 | GSL、GPR、OSAL、ACDB、ATS、日志工具库 | 源码 ATS 不等于私有 MCS 扩展已可互换 |
| FastRPC 音频启动器 | 小型 `cupid_audioadsprpcd` 包装器 | `libadsp_default_listener.so`、`libadsprpc.so` 保留匹配实现；没有整栈 ABI 替换结论 |
| GNSS | 公共 AIDL 服务、location 核心、QMI/socket/synergy 适配及 `libgnsspps` | `vendor.qti.gnss-service.so` 等私有扩展与设备固件 |
| 显示 HAL | gralloc、mapper4/Mapper5 兼容桥、两种 allocator 前端、composer、SDM core | Adreno GPU 用户态及特定私有显示扩展不是这些 HAL 的源码替代对象 |
| Thermal | QTI Android Thermal AIDL HAL、`libThermal_headers` 头文件依赖 | 固定 thermal-engine 仓库没有策略守护进程；不提供 `mi_thermald` 或 Xiaomi 内核桥的等价实现 |
| 虚拟内存 | `libvmmem` | 其消费者和配套内核仍需完整构建验证 |
| Wi-Fi、蓝牙、NFC | 清单/内核构建规则中已有的公共框架、HAL 和驱动源码 | 芯片固件、板级数据和私有扩展不因驱动源码化而消失 |
| 相机 | 公共 camera kernel techpack 和 Android 框架部分 | CamX/ISP 用户态、传感器调校及 Xiaomi 私有服务没有经核验的完整替代 |

`libsdmcore` 的定义在 `hardware/qcom/display/sdm/libs/core/Android.bp`。
`vendor/qcom/opensource/display-core` 是另一棵源码树，提供公共头文件和可选
SnapAlloc 实现；不能把其存在当作已选择 SnapAlloc 的证据。Cupid 仍需保持与
私有 CamX/Adreno 匹配的 gralloc4 private-handle ABI。

普通 XML、JSON、rc、权限声明等以 `prebuilt_etc` 或复制规则安装，是可读配置的
打包方式，不应和闭源 ELF 二进制混为一谈。构建工具链中的预编译编译器也不是
设备运行时 HAL；本轮不重建整个主机工具链。

## 如何检查

在完整同步、准备匹配 vendor 输入后，先按 [编译指南](BUILDING.zh-CN.md) 运行
`setup-makefiles.py`，再从 Android 根目录执行：

```bash
python3 device/xiaomi/cupid/tools/check_source_build_contract.py --top "$PWD"
```

产品解析时会自动运行同一预检。目录存在、开关名称含 `SOURCE`、或者构建目录里
曾经有 `.so`，都不足以证明当前产品实际从源码生成了该模块。

本次构建已生成包图后，继续执行：

```bash
python3 device/xiaomi/cupid/tools/check_source_build_contract.py \
  --top "$PWD" \
  --module-info out/target/product/cupid/module-info.json
```

预检只解析合同列出的定义与选择，不是完整的 Make/Soong 解释器。命名源码列表、
条件分支和传递依赖仍由实际构建求值；`module-info.json` 也必须来自本次源码。
最终需完成编译、ELF/镜像依赖检查及对应硬件回归，才能把该次产物标记为可用。
这些源码配置修改本身不构成已完成整包重编、刷机或长期稳定性验收的声明。

## 本轮改动的验证记录

- 设备侧 43 项 Python 行为测试通过，覆盖源码合同、同名预编译覆盖、旧目录升级、
  LF/CRLF 保留、重复执行及发生冲突前拒绝写入。
- 使用真实生成 vendor 元数据和公开 libvmmem 基线的 5 项集成检查通过。
- Linux 隔离目录使用服务器真实源码定义与本轮修改，完成规范化、再次检查、
  13 组共 36 个源码定义预检以及产品 Make 门禁检查；原 R6 文件摘要保持不变。
- Linux 上编译真实音频启动器，4 组 mock 运行测试通过，验证 `argc/argv`、
  `0x72` 重试、Cupid 保持 DSP 路径与 charger 启动行为，以及通用默认行为。
- 清单的 7 份 XML/source-policy 检查通过。

设备侧测试入口：

```bash
python3 -m unittest discover -s device/xiaomi/cupid/tests -v
python3 vendor/qcom/opensource/audio-hal/primary-hal/adsprpcd/tests/test_cupid_startup.py \
  --fastrpc-include external/fastrpc/inc
```

上述记录没有覆盖本次修改后的完整 Soong 包图生成、ARM64 Android 整包编译或手机
实测。主机上的 mock 运行不能代替真实 DSP、播放、录音、通话和温控等设备回归。
