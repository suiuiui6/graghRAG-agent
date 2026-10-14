# 依赖漏洞审计记录

> **日期**：2026-09-17
> **范围**：`backend/requirements.txt`
> **工具**：`uv tool run pip-audit`（版本随 `backend/uv.lock` 锁定）
> **CI 落地**：`.github/workflows/ci.yml` 的 `dependency-audit` job

---

## 一、审计结果

```
Found 5 known vulnerabilities in 1 package
Name     Version ID              Fix Versions
-------- ------- --------------- ------------
chromadb 1.5.9   PYSEC-2026-311                 (×2 重复行)
chromadb 1.5.9   PYSEC-2026-3814
chromadb 1.5.9   PYSEC-2026-3815
chromadb 1.5.9   PYSEC-2026-3813
```

**汇总**：1 个包、4 个唯一 CVE、**全部无 Fix Version**。

---

## 二、漏洞详情与可利用性判定

| CVE | 类型 | 影响路径 |
|-----|------|----------|
| PYSEC-2026-311 | 预认证代码注入（`trust_remote_code=true` + 恶意模型仓库） | ChromaDB **服务器模式** HTTP 端点 `/api/v2/tenants/{tenant}/databases/{db}/collections` |
| PYSEC-2026-3814 | 认证后代码注入（需 UPDATE_COLLECTION 权限） | 同上（default_tenant 端点） |
| PYSEC-2026-3815 | `SimpleRBACAuthorizationProvider` 只校验权限、不校验租户边界 | ChromaDB 服务端**鉴权组件** |
| PYSEC-2026-3813 | 缺失授权校验，任意认证用户可跨租户增删改查 | 同上 |

### 关键事实（已独立核实）

1. **本应用不使用 ChromaDB 服务端模式**
   - `backend/vector_store.py:64,71` 使用 `chromadb.PersistentClient`（**嵌入式**，进程内直连本地 sqlite/HNSW）
   - 全仓库**零处** `HttpClient`，**零处**读取 `CHROMADB_HOST` / `CHROMADB_PORT`
   - 4 个 CVE 全部作用于 **服务器模式的 HTTP 端点或其 RBAC 鉴权组件**，嵌入式客户端不经过这些代码路径

2. **但存在一处配置与代码不一致（需修）**
   - `docker-compose.yml:26,41-43` 起了 `chromadb/chroma:0.5.23` 服务容器
   - `docker-compose.yml:17` 给 backend 设了 `CHROMADB_HOST=chromadb`，并 `depends_on: chromadb (service_healthy)`
   - 即**部署意图是服务端模式，代码却从未连接**
   - 影响：一旦有人让代码读取 `CHROMADB_HOST`（compose 的明显意图），这些 CVE **立即变为可利用且静默**

3. **版本不一致的另一处隐患**
   - PyPI 包 `chromadb` 锁定 1.5.9，而 compose/CI 用的服务镜像固定 `0.5.23`
   - 两者不是同一版本线；若真要走服务端模式，需显式对齐

---

## 三、处置决策

**选择：声明当前不可利用 + 记录豁免（方案 A）**

### 理由

- 当前代码路径（`PersistentClient`）不经过任何受影响代码
- 4 条 CVE 均**无 Fix Version**：`PYSEC-2026-3813` 影响 `>=0.4.17`、`PYSEC-2026-3815` 影响 `>=0.5.0`，即**降级 python 包并不能解决**
- 升级不可行、降级无效、当前不可达 → 阻塞 CI 只会训练人忽略该 job

### CI 处置

`dependency-audit` job 保留 `--strict`，并逐条豁免上述 4 个 ID：

```
uv tool run pip-audit -r requirements.txt --strict --desc on \
  --ignore-vuln PYSEC-2026-311 \
  --ignore-vuln PYSEC-2026-3814 \
  --ignore-vuln PYSEC-2026-3815 \
  --ignore-vuln PYSEC-2026-3813
```

**每条豁免的复查触发条件（必须在下列任一情况发生时移除并重新评估）**：
- `backend/vector_store.py` 引入 `HttpClient` 或开始读取 `CHROMADB_HOST`
- `docker-compose.yml` 中的 chromadb 服务被真正接入应用
- chromadb 发布带 Fix Version 的新版本

### 未处置项

| 项 | 状态 | 说明 |
|----|------|------|
| chromadb 4 条 CVE | **豁免（不可利用）** | 见上；复查触发条件已列 |
| compose 中 chromadb 服务与代码不一致 | **待修**（独立任务） | 按铁律 7 需修一边：要么让代码接服务端、要么从 compose 移除该服务。推荐后者（当前无服务端需求） |
| 服务镜像 0.5.23 与包 1.5.9 版本线不一致 | **待决策** | 仅在决定启用服务端模式时才需处理 |

---

## 四、后续排期

1. **本任务**：CI 加 `--ignore-vuln` 豁免 + 本记录
2. **独立任务 A**：修 compose 与代码的不一致（推荐移除 chromadb 服务，或改为显式标注「预留未启用」）
3. **独立任务 B**：为 `dependency-audit` 增加 `on: schedule:` 周度运行，以捕获**已锁定依赖上新披露**的 CVE（PR 触发只在清单变更时重新评估，而新 CVE 披露与清单变更无关）

## 2026-10-13 后续核实（取代旧例外的当前执行结论）

后续[整改](../testing/2026-10-12-backend-dependency-remediation.md)已移除CI对Chroma四ID的忽略；锁闭包与新锁候选实际安装版本审计均保留5条原始记录/4唯一公告及exit1。本文历史PersistentClient可达性判断不能覆盖compose独立Chroma镜像，也不能作为当前扫描清零凭证。compose一致性、镜像扫描及必要升级/迁移仍未关闭。可选jieba与强传递依赖的测试规则见backend/CLAUDE.md：仅固定调用点例外加AST/行为验证，不使用全局依赖豁免。
