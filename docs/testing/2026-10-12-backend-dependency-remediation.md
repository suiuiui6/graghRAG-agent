# 后端依赖漏洞修复与锁一致性（2026-10-12）

## 修改前依据与方案

本任务为既有供应链问题维护，限定清单、锁及本文。读取根 AGENTS、memory 索引/日期记录、覆盖与扫描报告；遵循 systematic-debugging 和 verification-before-completion。backend 无独立 AGENTS。保留其他工作树改动，不修改 backend/.venv、不提交或推送。

原始扫描 `2026-10-12-pip-audit-locked.json`：205 个 registry 包，PyJWT 2.14.0 两条可修、multidict 6.8.0 一条可修、oauthlib 3.3.1 一条可修；Chroma 1.5.9 五条原始记录对应四个唯一 ID，暂无 fix_versions。

锁失败根因已由 `uv lock --check --offline --project backend --cache-dir .tmp/uv-audit-cache -v` 复现（uv 原始退出 1，日志 `.tmp/backend-lock-before.log`）：pyproject 的 dev 组已经有 ruff，旧锁的根 dependency group 没有 ruff。不是删除 dev 依赖来修复，也不是环境99包偏差导致该检查失败。

方案：PyJWT 下限升至2.15.1（2.15.0修安全问题，2.15.1恢复合法尾部Base64URL padding兼容性）；传递依赖以 uv constraint-dependencies 设置 multidict>=6.9.1、oauthlib>=4.0.0 安全下限，保留其传递角色，不增加伪直接依赖。仅定向锁到这三个版本，常规重锁保留其他已有包版本并补齐 ruff 等真实必要闭包。继续采用阿里云registry和原手写requirements策略，不 uv export 覆盖requirements。

oauthlib 4.0.0 是扫描提供的最低修复版本，虽然跨大版本，但不是系统核心组件替换。官方说明两项破坏变更为 token revocation 去掉JSONP、grant_type在客户端认证前验证；当前后端未实现 oauthlib OAuth服务端。仍需主进程在锁审查后同步并跑真实依赖回归，不能凭解析成功声称运行兼容。

官方依据：[PyJWT changelog](https://pyjwt.readthedocs.io/en/stable/changelog.html)、[multidict changelog](https://multidict.aio-libs.org/en/stable/changes/)、[oauthlib 4.0.0 release](https://github.com/oauthlib/oauthlib/releases/tag/v4.0.0)。后续验收为阿里云source全部保留、锁检查exit0、全锁重扫不再含三个已修包、未删除原包、无backend环境变更；Chroma不ignore并保留风险。

## Chroma 条件性例外复核

`backend/vector_store.py:64,71` 两条正常/回退路径均为 PersistentClient(path=self.persist_dir)，仅设置anonymized_telemetry=False；集合以固定name及hnsw/dimension metadata创建，无用户注入model仓库/trust_remote_code。既有例外为 `docs/governance/dependency-audit-2026-09-17.md` 的四ID，触发条件包括引入HttpClient、读取CHROMADB_HOST、真实接入compose服务或发布修复版。

但 `docker-compose.yml` 仍启动 chromadb/chroma:0.5.23，并设置CHROMADB_HOST/PORT及depends_on；镜像无host ports映射，不代表内部网络不可访问。Python锁扫描不覆盖该镜像。只能证明当前应用嵌入式调用不走已描述的HTTP/RBAC路径，不能推出整个部署零风险，亦不能用旧例外掩盖compose配置漂移。compose治理超出本任务文件所有权，交主进程处置。重扫保持全部Chroma发现和非零退出，不添加ignore。

## 执行与验证

已执行定向 `uv lock --upgrade-package pyjwt --upgrade-package multidict --upgrade-package oauthlib`，同阿里云索引；解析208包，升级三包并补ruff0.17.0，未整体upgrade。`uv lock --check` exit0；registry闭包206版本复扫仅chromadb1.5.9五条原始记录（四唯一ID），exit1，未ignore。原始证据 `2026-10-12-remediated-{lock-check.log,pip-audit-locked.json,pip-audit-locked-exit.txt}`。

发现并独立复审关闭安装入口未消费锁的缺口：Docker保持/app工作目录，langextract放/langextract，使用uv0.11.16 `sync --locked --no-dev --no-install-project`；CI签出子模块、sync锁、run --no-sync，audit从锁导出完整registry闭包，不再浮动requirements或无版本工具。CI导出参数本地exit0；Docker引擎不存在，镜像未构建。构建配置待真实CI/容器验证，不能称部署通过。

原环境sync预演需下载126包、卸载102、安装126，故未改变研究任务使用的backend/.venv。2026-10-13独立 `.tmp/backend-quality-venv-20261012` 同步exit0，实际安装186包（185 registry）版本与锁漂移0；安装版本复扫仍仅Chroma5原始记录/4唯一公告、exit1。候选全量回归暴露测试环境适配及旧研究冻结，已按独立审查修正测试导入/编码/可选分词契约，最终全量结果另见[整改接续](2026-10-12-quality-remediation.md)，不能把旧venv或局部专项当升级全部兼容证明。
