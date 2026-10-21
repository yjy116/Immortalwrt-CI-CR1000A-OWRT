# LuCI UPnP Regression Fixture

`luci.upnp` is unmodified upstream OpenWrt LuCI source from commit
`0a601b651af34ae4a83dd89f417dccdc474ec348`, path
`applications/luci-app-upnp/root/usr/share/rpcd/ucode/luci.upnp`.
Its Apache-2.0 license notice is retained in the file.

The counter-bearing TCP rule in the test was read from CR1000A's actual nft
ruleset on 2026-10-21. UDP and nonzero-counter cases are explicit synthetic
fixtures. The Python matcher checks the shared regular-expression subset;
deployment is additionally verified with native ucode and actual LuCI RPC/UI.

The proposed upstream fix is OpenWrt LuCI PR #9148, commit
`9f52246f6fc40420be8ee962502ac967f0f3ec26` (unmerged when adopted).
