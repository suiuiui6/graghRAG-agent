# R7 SQLite运行库发现与派生组合实证

范围：root实际执行的隔离runtime发现/组装与ABI初验，不是完整原型或生产安全准入。原runtime debugger因账号usage中断，后续下载、组合及测试由root完成，不冒称Agent独立执行。独立设计/PE检查见同日sqlite-numpy-runtime-review。

## 官方原构建及真实失败

固定Astral python-build-standalone release `20261013`，资产 `cpython-3.12.15+20261013-x86_64-pc-windows-msvc-install_only_stripped.tar.gz`，官方asset ID638902136、22,019,610 bytes。GitHub官方SHA256 `7a2aef48e5ee569e310b29b32681debbc5d888e92790d85331a47736c6b06aad`；实际完整下载匹配。直链首次timeout exit28，续传因持续低速手动中断，官方资产API有界180秒timeout124；未完整部分文件未执行。最终经npmmirror传输25秒完成，执行前与已冻结GitHub官方摘要及大小完全匹配。镜像仅传输，不作为来源/安全证明；原始官方构建身份不改。

原构建实际Python3.12.15，标准库SQLite **3.53.1**，source_id及loaded modules已记录。新解释器版本不能推出SQLite已修；`r7_sqlite_floor.py`对该精确构建实际exit1。最低3.53.2依据[SQLite官网已列公告](https://sqlite.org/cves.html)，不以连接硬化绕过版本准入。本轮不安装APSW或修改原DLL。

## 新派生组合

独立局部设计评审允许在新profile验证“官方Python＋官方SQLite DLL”组合，不能承袭上游官方整体支持或完整测试声明。原base、系统及旧venv保留，项目生产未动。

[SQLite官方页面](https://sqlite.org/download.html)的固定Windows x64 `2026/sqlite-dll-win-x64-3540000.zip`，3.54.0，1,450,308 bytes，官方SHA3-256 `f5fb500c73a3afd89976386bb8e4fdc8b5b65c052e187fb1ada1f5de034cd45b`，实际匹配。ZIP仅读取固定 `sqlite3.dll`，其SHA256 `5ca6a16bdd2c5a5037b1e3a942d9ac1c66efe2def902b202d44774680a8a4656`。

root组装脚本先保存完整base文件hash，复制至新derived目录，仅更新新副本`python/DLLs/sqlite3.dll`。完整before/after清单断言只有这一项变化、base前后相同。派生解释器路径 `.tmp/sqlite-runtime-r7-20261015/derived/python/python.exe`；这属于项目派生组合，不是未修改的官方完整发行版。

## 实际初验及边界

`build_r7_derived_runtime.py`正规require_escalated执行exit0：原floor red1→派生floor green0；新实际SQLite3.54.0、动态已加载SQLite DLL路径在derived目录且SHA匹配官方DLL。参数绑定BLOB内存往返成功；defensive初始false→显式true、trusted_schema初始1→0、extension初始false→显式false，SQL加载扩展被拒绝。未硬化的新连接默认仍非安全配置，后续原型每连接必须核设置。

独立PE只读检查：Python `_sqlite3.pyd`需要88个sqlite3_*命名导入，新DLL379个命名导出全部覆盖；二者Machine0x8664/PE32+。仅证明名称/架构匹配，不能代替实际ABI与完整行为测试。root记录实际OpenSSL3.5.9（2026-09-29）、zlib1.3.2、expat2.8.5及全部可见已加载模块/文件hash；这是身份记录，不是所有原生组件零漏洞结论。

本报告初验时原型仍在TDD实施，事务/backup/多进程/中止恢复/NumPy及独立新输入尚待最终冻结验收。完整CPython测试套件、Python所有模块/Windows CRT全面公告及构建attestation验证未执行，不能宣称生产整体安全或替换已完成。

## 机器证据入口

最终追加：运行库证据已逐hash永久归档到[28文件清单](../testing/sqlite-runtime-r7-20261015/archive-manifest.json)，[验证后profile复核](../testing/sqlite-runtime-r7-20261015/post-validation-profile-check.json)显示原与派生全树均无内容漂移或新增文件。随后固定schema原型作者9项、root复制9项以及独立作者9项＋新输入2项全部exit0，事务、backup、多进程锁及中止恢复在声明域完成验证；详情见[最终报告](../testing/2026-10-15-sqlite-numpy-runtime.md)。上文“初验时待最终冻结”是历史状态，现以此追加为准。完整运行库原生安全审计及生产准入仍未完成。

源证据 `.tmp/sqlite-runtime-r7-20261015/`：`artifact-receipt.json`、`api-download-receipt.json`、`mirror-download-receipt.json`、原`runtime-native.json`、`floor-red.log/.exit`、`floor-green.log/.exit`、`derived-composition.json`、`derived-probe.log/.exit`、`derived-evidence/runtime-native.json`、`sqlite-official/sqlite-artifact-receipt.json`和`download.html`。root负责最终逐hash归档到docs/testing及状态回流；没有依赖主锁或生产变更、没有提交/推送/部署。
