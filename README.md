# CR1000A OWRT CI

本仓库专门为 Verizon CR1000A 编译 **owrt 分支**，源码取自 [yjy116/immortalwrt 的 owrt 分支](https://github.com/yjy116/immortalwrt/tree/owrt)。一次触发同时构建 WiFi-YES 和 WiFi-NO。

这是独立的公开 CI 仓库；原 [Immortalwrt-CI-CR1000A](https://github.com/yjy116/Immortalwrt-CI-CR1000A) 及源码 fork 的 `main` 分支不变。CI 文件仍存放在本仓库的 `main` 分支，**固件源码分支是 `owrt`**，两者不要混淆。

This public CI builds both CR1000A WiFi variants from the controlled `yjy116/immortalwrt:owrt` source branch. The existing main/NSS CI and source branch remain separate.

## 配置来源

2026-10-30 核对基线（实际源码提交以每次 Release 为准）：

| 用途 | 仓库与提交 |
| --- | --- |
| 编译模板 | [VIKINGYFY/OpenWRT-CI · 64b8aead](https://github.com/VIKINGYFY/OpenWRT-CI/tree/64b8aeadde2ea4ac97a40be56d51bda4c43882ed)，采用通用配置及适用的脚本更新 |
| 固件源码 | [VIKINGYFY/immortalwrt owrt · fd622baa](https://github.com/VIKINGYFY/immortalwrt/commit/fd622baa05b8adf55970ecfb123f9c3fed0f23a8)，Linux 6.18；核对时用户 fork 已与此提交一致 |
| 补充插件 | [Immortalwrt-CI-JDC-AX6600 · 7cedfb8](https://github.com/yjy116/Immortalwrt-CI-JDC-AX6600/tree/7cedfb8b79528d461075bdbd8ac0a7eff7e0be5e) |

- `Config/GENERAL.txt`：完整采用上游模板的通用配置。
- `Config/CR1000A-WIFI-YES.txt`、`Config/CR1000A-WIFI-NO.txt`：采用上游 IPQ807X 有无线/无无线设置，只选 CR1000A，均显式启用原生默认包 `kmod-dsa-rtl9303-spi`、`cr1000a-recovery`、`kmod-nss-wifi-drv`。
- `Config/EXTRA.txt`：AX6600 补充插件、后续已选插件及所需依赖，本次保留全部既有选项并新增上游 PPE QoS。以后增减这些插件优先修改此文件。
- 配置合并顺序：设备配置、GENERAL、EXTRA、Settings 中的 PRIVATE 和手动 PACKAGE；私有配置与手动参数仍可覆盖普通插件选项。
- `Scripts/Packages.sh`、`Handles.sh`、`Settings.sh` 使用上游模板结构，补入插件源和必要的插件兼容处理；处理失败会明确报错。
- 默认主题与模板一致，使用 Aurora。保留本项目的设备名称、网络默认值、Auto-Build 原有调度、预热缓存和手动缓存清理。不恢复 `apt full-upgrade`，也不引入模板的浮动 Rust 编译器覆盖或自动缓存删除；并非整套 workflow 无差别覆盖。

## 硬件支持

LAN、WAN、无线及升级流程采用 owrt 上游实现，不注入本地 no-PHY 补丁、强制链路、LAN 转发表、VLAN 初始化或 `yjy116/files` overlay。设备树、板级网络初始化、RTL9303 驱动及恢复脚本保持上游原样。

- 有线：使用 PPE/EDMA 和 RTL9303 SPI DSA，默认 LAN 接口为 `lan1`、`lan2`、`lan3`，WAN 为 `wan`，不再使用 main 分支的 NSS/ECM/SSDK 和厂商用户态交换机初始化程序。
- 硬件包：选择 `kmod-dsa-rtl9303-spi`、`cr1000a-recovery` 与新的 `kmod-nss-wifi-drv`，配置展开和产物清单均检查。owrt 已移除 `cr1000a-support`，此处不再选择或补回它。
- 升级：沿用上游 eMMC、FIT 大小和恢复镜像校验流程。上游 CR1000A FIT 限制为 20 MiB；这不是 rootfs 或 eMMC 总容量限制，不在 CI 中覆盖这些限制。
- SQM：保留 LuCI 页面，使用标准 `sqm-scripts`，不再选择 `sqm-scripts-nss`。旧 NSS 队列脚本配置不能直接套用；整形与流量卸载的实机效果仍需验证。

WiFi-YES 使用上游 ath11k 驱动、QCN9074 固件及 CR1000A 板级数据，采用新 `ATH11K_NSS_WIFI` 集成。WiFi-NO 保留上游对 ath11k AHB/PCIe 驱动及 IPQ8074/QCN9074 无线固件的禁用配置，并使用 `ipq8074-nowifi.dtsi` 调整 Q6 预留内存，不提供板载 WiFi。启用按设备打包后，`make defconfig` 仍可能将无线包展开为 `=m`，表示构建模块包，不等于装入基础 rootfs 或开启无线。**两种模式均保留原生 LAN/WAN 及新 NSS 驱动**；上游启动脚本根据实际安装的无线驱动和可用硬件选择 `wlan`，无可用无线总线时使用 `wlan=0`，不是只看编译期 `ATH11K_NSS_WIFI` 开关。编译成功不等于原生 6GHz、全部 LAN 口或实际吞吐已通过验证。

### 原生 PPE/NSS 与 PPE QoS

上游 [d4edc748](https://github.com/VIKINGYFY/immortalwrt/commit/d4edc7481a9f14b549575dd2cc849a902797055c) 引入新的 PPE/NSS 协作方案，[3dfd706f](https://github.com/VIKINGYFY/immortalwrt/commit/3dfd706f58c16bc86563930cfbbaea0207f06c54) 将 NSS 与无线包选择解耦。本项目直接使用这些源码，不再叠加历史 main 分支的 ECM、SSDK 或旧 NSS 补丁。

- 普通有线单播继续走 PPE/EDMA；新 NSS 负责支持的无线数据路径及 USB/raw-IP 等重定向场景。不是所有 VPN、隧道或代理流量都可卸载，不承诺代理插件获得额外加速。
- 沿用上游 `nss-wifi` 默认值 `offload=1`、固件 `12.5`。改变 NSS 数据环所有权/卸载模式需要按上游要求重启；本仓库不会修改运行中设备。
- 新增上游 `luci-app-qca-ppe-qos` 和 `qca-ppe-qos`，页面位于 **网络 → PPE QoS**，用于硬件分类、DSCP 和优先级。它与 SQM 限速/队列管理互补，保留现有 SQM；使用上游 QoS 默认规则，不额外预设带宽或覆盖用户配置。
- 上游报告的流量测试设备为 AX6/RE-CS-02，不能当作 CR1000A 已通过验证；PPE QoS 作者也未声明运行时验证完成。新固件仍需实机确认 LAN/WAN、无线、代理及 SQM 交互。

`Scripts/CheckOwrt.sh` 在 `make defconfig` 后检查原生 DSA、恢复、NSS 与 QoS 配置。WiFi-NO 拒绝无线驱动包选为 `=y`，但允许上游按设备打包产生的 `=m` 及编译期 NSS 无线集成；WiFi-YES 仍要求三个无线驱动包和 NSS 集成。发布前核对通用 `.manifest` 中显式内置的原生公共包，并拒绝 WiFi-NO 基础清单中出现无线驱动。**该清单来自 `TARGET_DIR_ORIG`，不是各设备追加包后的完整清单**，不能用它单独证明设备镜像中的全部无线包是否存在。Release 附带 `PPE-NSS-SOURCE.txt`，记录源码提交、模式、四份原生包 Makefile 的 SHA256 和关键配置；最终设备镜像内容及实际无线状态仍需分别核对，不把这些检查当作完整编译或刷机测试。

**从 main/NSS 固件迁移：** 先备份设置并准备恢复手段，建议不保留旧网络配置刷入，再按新接口重新配置 LAN/VLAN。不要直接恢复旧 `/etc/config/network`、NSS SQM 或硬件 overlay。若手工迁移 `/etc/rc.local`，移除旧 `/lib/rtl/init.sh`、`/lib/aqr/init.sh`、`/lib/mmc/init.sh` 及 `exec-dir`/switch 调用，保留其他自定义命令。这里不自动删除路由器上的用户配置，也未验证从每一种历史固件跨架构升级的安全性。

### 6GHz 无线默认配置

2026-10-18 核对了 [CI 模板 5a77a38](https://github.com/VIKINGYFY/OpenWRT-CI/tree/5a77a388c8fe91c894f3e97618e9f997b57c4fba) 和 `26.10.17-10.45.55` 的实际 WiFi-YES 镜像：QCN9074 固件及 CR1000A `board-2.bin` 均已打包，配置中的 `=m` 属于按设备 rootfs 的正常包选择，不能据此判定漏包。

`Settings.sh` 跟随新模板直接定制 `mac80211.uc` 的默认值，不再走旧 `set-wireless.sh` 分支，**不额外使用无线补丁文件**。上游 UCI 默认写 `psk2+ccmp`，但当前 ucode 后端会在 6GHz 自动映射为 SAE，因此不能把旧 UCI 字样当成实机使用 WPA2 或无线故障的证据。本项目显式填写 6GHz 的 SAE 默认值，使配置意图更清晰；上游必需字段消失时明确报错，不静默跳过。

设备主人确认实际使用地区为 **US**，并计划不保留配置升级，首次启动默认值如下：

| 项目 | 默认行为 |
| --- | --- |
| 国家/地区 | 所有射频设为 `US`；由两个入口 workflow 的 `WRT_COUNTRY` 传入 |
| 6GHz SSID | `CR1000A-6G`，沿用 workflow 配置的 WiFi 密码 |
| 6GHz 安全 | WPA3-SAE；PMF-required 和 SAE H2E 由原生 hostapd 处理 |
| 频段 | 上游自动检测 PHY 能力，支持 6GHz 时优先选择，不硬编码 radio2 |
| 信道和带宽 | 上游默认信道，未给出时为 auto；上游带宽上限 80MHz，不强制 160MHz |
| 功率模式 | 原生 hostapd 的 6GHz LPI 默认值，面向室内使用；不提高发射功率 |
| 2.4/5GHz | SSID 与加密沿用原默认，国家码同样使用实际所在地 US |

这只是无线配置生成修复，**不是第三射频实机验证通过的声明**。驱动、设备树、板级数据和 PHY 检测继续跟随 owrt。若固件/PHY 未上报 6GHz 能力，不能靠改名称或强制频段解决。设备改到其他地区使用前，应同步修改正式及测试 workflow 的 `WRT_COUNTRY`，并核实当地允许的信道。

- 新生成的无线配置才使用此默认值；保留配置升级不会覆盖已有 `/etc/config/wireless`。
- 若现有 6GHz 接口仍使用 WPA2，在 LuCI 中将该接口改为 WPA3-SAE，并按实际所在地设置国家/地区。不要靠改成其他国家绕过信道限制。
- 若仍无 6GHz，提供 `iw phy`、`iw reg get`、`ubus call network.wireless status` 和最新内核/系统日志，区分未识别射频、无可用信道与 hostapd 启动失败；分享前遮掉密码和其他敏感信息。

The owner confirmed US operation. Fresh wireless settings use US, a separate 6GHz SSID and WPA3-SAE; native owrt detection, drivers and channel/power rules are retained. Existing settings are not overwritten and hardware operation remains unverified.

## 插件补充

在模板的 HomeProxy、GecoosAC、Mini DiskManager、NATMapT、Samba、UPnP、WOLUltra 等基础上，增加：

- 代理：DAE、DAED、统一 `luci-app-daede`、Nikki、Passwall、OpenClash。
- 联网与服务：AdGuardHome、EasyTier、Tailscale、ZeroTier、WireGuard、标准 SQM、PPE QoS、DDNS-Go、Lucky、USB 打印、VLMCSD、SoftEther VPN。
- 工具：qBittorrent、TTYD、CPUFreq、Statistics、VnStat2、Btop、Tcpdump，以及参考仓库的通用存储/诊断工具。
- GeoData 更新器：保留参考项目的功能和每周更新时间，数据包仍使用上游 feed，不重复定义；下载及 SHA256 校验失败返回非零，不替换旧数据，不使用第三方下载代理。

HomeProxy/sing-box 按模板从 `VIKINGYFY/packages` 配套获取，不再保留旧的“官方 feed 专供”处理，不单独强升 sing-box。

保留 NATMapT。其核心 [NATMap](https://github.com/heiher/natmap) 面向兼容的 Full-cone NAT 映射，并非 UPnP 的重复组件；没有独立公网 IPv4 不代表它无用，也不代表任意 CGNAT 都能穿透。只有需要让外部设备通过公网端口访问内网服务时才需配置；尚未对用户当前上级 NAT 做可达性测试，不能承诺成功。

DAE/DAED 使用参考项目的 `kenzok8/openwrt-daede@0b0e5d6`，包括后端切换互斥、旧订阅任务迁移和错误上报修复。使用内核 BTF，不额外携带大型 `vmlinux-btf`；准确源码信息随 Release 的 `DAEDE-SOURCE.txt` 发布。迁移保留旧数据库/配置和订阅计划；自动更新凭据需在新界面中核对。

### Honk + Doona（实验性）

新增 [kenzok8/openwrt-honk](https://github.com/kenzok8/openwrt-honk/tree/b733aadc69b0d3c618104241972f483adda97aed) 的 `honk` 和 `luci-app-honk`，Doona 页面及中文翻译随 LuCI 包安装，没有单独的 `doona` 配置项。正式与测试工作流的两种 WiFi 模式均包含它们。

- 固定打包提交 `b733aad`、Honk native-api 核心 `Glassyiris/honk@0e61ed3`（alpha）和 `Zakkaus/doona@34657ab5`（beta.20）。它不是直接替换为 `daeuniverse/honk/main`；Doona 需要配套 native API。
- `Scripts/Honk.sh` 获取固定 `source-39098804282` 发布的元数据并校验 SHA256；构建系统再校验核心和 UI 归档。缺文件或哈希不匹配直接失败，不使用浮动 staging/跳过校验。
- 使用已编译的静态 AArch64 核心及 Doona 静态资源，由本仓库的 owrt 构建系统重新打包，不直接安装其他 SDK 的 IPK，也不增加整套 Rust/Zig/Node 编译链。
- 复用内核 BTF 和已有 GeoData，补齐 Function/Dynamic Ftrace 支持，不携带 `vmlinux-btf`。已核对核心裸文件约 25.83 MiB、Doona 解包约 3.28 MiB；这不是最终固件的净增大小，最终压缩体积和分区校验以本次构建为准。
- **默认关闭、不自启、未初始化**。刷机后在 LuCI 的 Honk 页面显式初始化、设置登录凭据后再启用；Doona 由 Honk 提供，初始化后监听 LAN 地址的 9527 端口，不另起服务。
- 保留 DAE/DAED。Honk 与它们共用 `dae0` / `daens` 等资源，不能同时接管流量；切换前先正常停止当前透明代理，不要强杀。启停保护会明确报告冲突，不能以改端口代替互斥。

版本和组件来源随 Release 的 `HONK-SOURCE.txt` 发布。后续更新需同时核对 `Scripts/Honk.sh` 中的提交、资产标签、三份元数据哈希及配套服务兼容补丁，不能只改核心版本号。当前仅完成源码、资产和构建配置接入检查，BPF verifier/fentry、PPE 交互及真实 TCP/UDP/DNS 流量仍需刷机后验证。

不引入 AX6600 的 Athena LED、内存/设备配置及其他硬件补丁；不恢复 netspeedtest 源，也不启用 MosDNS、speedtestcpp 或旧 luci-app-speedtest。测速采用模板的命令行 iperf3，不保留旧的独立 luci-app-iperf3。

2026-10-17 核查发现模板中的 `lmq8267/luci-app-vnt` 返回 404，匿名 Git 无法访问。本项目未启用 VNT，因此不再下载该源，避免无关插件阻断构建；其他包源下载失败仍会明确报错，不会静默跳过。

新增插件会增加固件大小和编译耗时。最终镜像大小、设备分区容量和实际可用空间仍需在构建及刷机前核对，不能用 eMMC 总容量代替固件分区容量。

## 构建和缓存

### MiniUPnP 重连修复

MiniUPnP 官方 `2.3.11` 在 WAN 短暂断线后重新获得私有/CGNAT 地址时，可能一直拒绝端口映射，直到重启服务。官方修复为 [2dcf639](https://github.com/miniupnp/miniupnp/commit/2dcf63959950dbb2c3f97b7bd63773d499749134)。项目不维护额外的本地 C 源码补丁，由 `Scripts/Miniupnpd.sh` 自动选择：

- feed 版本不高于 `2.3.11`：使用官方修复源码，打包为 `2.3.11-r2`；同时取用 ImmortalWrt packages 的固定提交 `72c7391` 中完整的 miniupnpd 包目录。源码和打包归档分别校验 SHA256，避免未来 feed 的新补丁、启动脚本与旧核心混搭。保留该快照原有的服务、防火墙集成和兼容性补丁，不修改 LuCI 或默认权限。
- feed 升级至更高正式版本：通过 GitHub API 确认对应 MiniUPnP 官方 release tag 的历史包含上述修复，然后原样使用 feed 包，不再固定旧核心，也不替换新版的启动脚本或补丁。正常发布无需手工改版本和哈希。
- 下载、校验或官方修复确认失败会明确报错，不静默降级。版本号格式、源码来源变化或上游以不同提交重新实现修复时需要人工复核；不能保证未来版本不存在新缺陷。

固定源码元数据在 `Config/miniupnpd-source.mk`，打包快照及其哈希在 `Scripts/Miniupnpd.sh`，两种 WiFi 固件共用。Release 的 `MINIUPNPD-SOURCE.txt` 记录实际选择的来源、版本和校验依据。新版核对使用 CI 已有的 `GITHUB_TOKEN`，不需要另加密钥。

此修复恢复的是本机端口映射，不会替运营商配置 CGNAT，也不保证公网入站可达。未安装新固件的设备仍是旧核心，单独重启 `miniupnpd` 只能暂时恢复。无需清理工具链缓存；不会在运行中的路由器上自动重启代理或网络服务。

### LuCI 端口映射显示

新版 MiniUPnP 的 nftables DNAT 规则包含 `counter packets ... bytes ...`，旧版 `luci-app-upnp` 的状态读取器无法匹配，可能出现实际映射有效、LuCI 却显示空列表的问题。

项目回移 [OpenWrt LuCI PR #9148](https://github.com/openwrt/luci/pull/9148) 的原始单行修复，提交为 `9f52246f6fc40420be8ee962502ac967f0f3ec26`。截至 2026-10-30 该 PR 已关闭但未合并，OpenWrt/ImmortalWrt 的读取器仍存在旧匹配式，不能视为官方已发布修复。未采用包含 UCI/访问控制迁移的整体重构，也未替换 LuCI 包、MiniUPnP 核心或其服务配置。

`Scripts/LuciUpnp.sh` 在两个 WiFi 模式共用的构建步骤中处理 feed：旧读取器应用原始上游补丁；已包含该修复的 feed 保持原样，不重复应用。若将来读取器整体重构、补丁和反向校验均不匹配，构建明确提示复核，不覆盖新版实现或静默宣称兼容。上游正式合入后可移除这项回移；无需因普通版本号变化手工更新。

Release 附带 `LUCI-UPNP-SOURCE.txt`，记录本次使用原生 feed 还是上游回移，以及修复提交和最终 RPC 文件 SHA256。验证应创建短租期临时映射、同时检查 LuCI 与真实规则，最后通过 UPnP 协议删除；现有 LuCI 的“删除”按钮会重启 MiniUPnP，不适合无中断诊断。本构建脚本不操作运行中的任何服务。

### 触发编译

手动运行 Actions 中的 `CR1000A` 或 `CR1000A-test`，**一次触发同时启动 WiFi-YES 和 WiFi-NO 两个并行任务**，不需要分别选择或触发。两种模式共用 GENERAL/EXTRA 插件清单，分别生成独立 Release，标签以 `CR1000A-WIFI-YES-` / `CR1000A-WIFI-NO-` 开头，固件文件名包含 `wifi-yes` / `wifi-no`。某个任务失败不会自动取消另一个任务。

将 `TEST` 设为 true 时仍会启动两个任务，但只生成两种配置，不编译固件。构建主机继续跟随模板使用 `ubuntu-latest`。原有 Auto-Build 调度及新提交检测逻辑不变，只把检测分支改为你 fork 的 `owrt`。WiFi-NO 请通过有线网络管理；不要通过手动 PACKAGE 或 PRIVATE 配置重新启用无线驱动，否则会与无无线内存布局冲突。

2026-10-30 的运行 `40994067733` 分配到 Ubuntu 26.04，两种模式均在初始化阶段被旧 `init_build_environment.sh` 的系统白名单拒绝，尚未下载固件源码。环境依赖现跟随模板通过 `apt-get install --no-install-recommends` 显式安装，保留原有 `libfuse-dev`，不再调用该外部安装器；不伪装系统版本、不忽略安装错误，也不恢复 `full-upgrade`。这是构建主机适配，不改变固件内核或插件选择。

FullCone 已使用 `Config/GENERAL.txt` 的 `CONFIG_PACKAGE_fullconenat-sonic=y`，没有选择旧 `kmod-nft-fullcone`。owrt 的 SONiC 实现集成到原生 NAT 模块，并禁止与旧 FullCone 包共装；不要为此次环境初始化错误补回旧模块。主机及配置检查不能代替完整构建和刷机验证。

### 受控更新源码

本 CI **不会自动同步 VIKINGYFY 源码到你的 fork**。需要升级时，先核对上游 owrt 的变更，再手动同步你 fork 的 `owrt` 分支，然后触发本仓库构建。不要把 `main` 合并进 `owrt`，也不要以为只同步 fork 的默认 `main` 就更新了 owrt。

使用 GitHub CLI 可单独同步该分支（不要加 `--force`，若存在分叉应先检查）：

```sh
gh repo sync yjy116/immortalwrt --source VIKINGYFY/immortalwrt --branch owrt
```

这里隔离的是主源码；feeds 和第三方插件仍按现有模板在构建时获取，未全部锁定。Release 中记录实际源码提交和 DAEDE 版本，方便追溯。

正式和测试工作流共用兼容性缓存规则：源码仓库/分支、平台、构建工具/内核源码、GENERAL/EXTRA/设备配置和构建主机共同生成指纹。WiFi-YES 与 WiFi-NO 使用各自的兼容性指纹，不混用缓存；首次切换到新配置名称需要重新预热。相关变化自动使用新缓存，不匹配旧的宽泛缓存键。

没有兼容缓存时，先预热 `tools` 和 `toolchain`，成功后立即保存；完整编译成功后再保存完整缓存。仅缓存 `.ccache`、`staging_dir/host` 和交叉工具链，feeds 的 `hostpkg` 重新构建。继续使用 `actions/cache@v5`。

怀疑缓存污染、重要源码变更后反复失败，或希望完整重新预热时：

1. 打开 Actions，选择 `Cache-Clean`。
2. 点击 `Run workflow`。

这会清空本仓库 Actions cache，不删除 Release、固件、源码或运行记录。首次重建较慢；无需另设周期性缓存清理。

## 本地验证

需要 Bash、Python 3 和 Node.js。准备上述固定版本的 **owrt 源码**、CI 模板及 AX6600 参考仓库：

```sh
export WRT_SOURCE_CHECK=/path/to/immortalwrt-owrt
export WRT_CI_TEMPLATE=/path/to/VIKINGYFY-OpenWRT-CI
export WRT_PLUGIN_REFERENCE=/path/to/AX6600-CI
export GITHUB_WORKSPACE="$PWD"
bash Scripts/Honk.sh /tmp/cr1000a-honk-check
export WRT_HONK_CHECK=/tmp/cr1000a-honk-check
export MINIUPNPD_PACKAGE_CHECK=/path/to/immortalwrt-packages/net/miniupnpd
# Download the official commit archive referenced by Config/miniupnpd-source.mk.
export MINIUPNPD_ARCHIVE_CHECK=/path/to/miniupnpd-2dcf639.tar.gz
# Immutable packaging archive from the commit in Scripts/Miniupnpd.sh.
export MINIUPNPD_PACKAGING_ARCHIVE=/path/to/packages-72c7391.tar.gz
python3 -m pip install -r Tests/requirements.txt
python3 -m unittest discover -s Tests -v
bash Scripts/Daede.sh /tmp/cr1000a-daede-check
bash Tests/test_daede_migration.sh
bash Tests/test_daede_service_guard.sh /tmp/cr1000a-daede-check
bash Tests/test_honk_coexistence.sh /tmp/cr1000a-daede-check /tmp/cr1000a-honk-check
node Tests/test_daede_switch.cjs /tmp/cr1000a-daede-check
bash Tests/test_mihomo_conflicts.sh
bash Tests/test_geodata_updater.sh
```

检查覆盖双模式并行矩阵及 owrt 分支、WiFi-NO 上游禁用项和 Q6 调整、缓存隔离、模板/插件差集、DSA/恢复/NSS/QoS 配置和 manifest 缺包报错、原生 LAN/WAN/升级/NSS/QoS 文件不被改写、第三射频板级数据、无线默认值转换、Honk/Doona 发布输入，以及 DAE/DAED 迁移和切换。服务测试只替代路由器专有 I/O，不代表实机运行；完整固件仍由 GitHub Actions 验证。
