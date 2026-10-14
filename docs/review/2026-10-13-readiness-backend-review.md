# 2026-10-13 后端 readiness 独立评审

## 审查总结

独立只读审查本轮 TableIndex、守卫测试、生命周期删除边界及研究冻结的软件契约。查询值已通过 DuckDB Expression 绑定，守卫新增测试执行真实 callback 且保留真实子进程测试，冻结断言没有把漂移改判为研究通过；发现生命周期激活版本删除阻断及查询整体资源界不足。

首轮问题统计：Critical 0、High 1、Medium 1、Low 0。首轮结论：生命周期修复前不可关闭本轮安全评审；专项通过不代表全量双覆盖率、扫描或发布门槛通过。

遵循当前 AGENTS → memory/index.md → memory/2026-10-13.md → docs/plans/2026-10-13-quality-to-90.md。using-superpowers 已读取，其 SUBAGENT-STOP 对本独立子任务适用；按 requesting-code-review 的独立评审原则适配执行，不递归派发评审，不启动 goal/Harness。分支 master，HEAD 46b202c3e400741fd569f024412c0745f224a538，大量其他未提交修改保留；仅拥有本报告。

## 问题清单

### 🟠 High：激活旧版本会被实际删除

- 文件：`backend/services/lifecycle.py` 首轮行 220–252；关联 `backend/kg_store.py` 行 381–387、企业蓝图 §5.6。
- 描述：路径修复使删除真实生效，但 `_find_expired_versions()` 仍简单取 `versions[:-10]`，不读 `versions.json.active_version`。用户回滚激活较早版本后会删掉当前图谱，元数据仍指向已删除目录。蓝图明确 active 永不删除，`keep_active=True` 未实现。
- 独立真实临时复现：建 v0..v11 与 active_version=0 的 manifest；输出 candidates=[doc_1/v0, doc_1/v1]、removed=2、active_v0_exists=false、active_metadata=0。该复现只操作 `backend/tests/_sandbox_tmp/active-review-*`，不操作用户图谱。
- 建议：严格读取有效 active 元数据、排除 active 后按最多保留十个选择最旧版本；元数据缺失/损坏/类型无效应 fail closed。保留绝对 resolve containment；加真实 manifest 回滚与异常测试。
- before/after（示意，不是已落地代码）：

```python
# before
expired.extend(str(v.relative_to(KG_DIR)) for v in versions[:-10])
# after: metadata validated; never choose active
eligible = [v for v in versions if v.name != f"v{active}"]
expired.extend(str(v.relative_to(KG_DIR)) for v in eligible[:max(0, len(versions)-10)])
```

关联消费者风险：清理后版本列表不能让 `activate_version()` 接受缺失目录。如果删除 manifest 条目，`create_version()` 当前 `len(versions)+1` 会重复编号并覆盖保留目录，应验证单调版本号或保留可追踪清理历史，不能直接删除列表条目了事。以上均已立即报告协调者。

### 🟡 Medium：仅单条限制没有整体谓词与 limit 边界

- 文件：`backend/table_index.py` 首轮行 24–43、117–120、254–273。
- 描述：每条限制 2048 字符/256 token/16 层，但 conditions 列表长度不受限，最终 AND 表达式仍可无限增长。非负整数检查接受超出 DuckDB signed64 能力的 top_k；同样的 `2**63` 在无条件查询抛 TypeError，而有条件查询被吞成空结果。
- 独立小规模探测：256/1024/2048 条相同短谓词均成功执行，分别约 0.040/0.381/1.335 秒；单条上限不能约束整体开销。没有执行大规模耗尽探测。该项是资源/异常契约问题，不宣称存在 SQL 注入。
- 建议：在编译前明确谓词总数/总字符上限；top_k 校验 DuckDB 可表示范围，统一 ValueError，避免非法输入伪装零命中。
- before/after（示意）：

```python
# before
if type(top_k) is not int or top_k < 0:
    raise ValueError(...)
# after
if type(top_k) is not int or not 0 <= top_k <= MAX_QUERY_LIMIT:
    raise ValueError(...)
if not isinstance(conditions, list) or not 1 <= len(conditions) <= MAX_PREDICATES:
    raise ValueError(...)
```

## 已核实的有效行为

1. TableIndex 不再拼接 conditions 或 limit 到 SQL；列名按实际列集合验证，字符串/数值用 ConstantExpression。DDL 的 identifier sanitizer 仅保留字母数字下划线，查询 projection/order 为固定语句。注释、函数、子查询、分号、未知字段、非有限数值、过深嵌套均拒绝；真实 DuckDB 断言覆盖 EAV、转义单引号、AND/OR 优先级、NULL、宽表回退及 zero limit。此 grammar 有意缩小为列与字面量比较；不把任意旧 SQL 都声称兼容。
2. `test_guard_readiness.py` 只拦截不可逆注册和 native loader 边界；实际 install_guard 的 callback 与路径检查执行，断言 PermissionError、blocked 计数、允许操作与 loader 实际收到的绝对路径。临时 lstat stub 验证类型分支，真实 hardlink 与既有 child-process 测试补足运行行为，不能互相替代。
3. 生命周期 resolve containment 对根目录自身与越界目标拒删，真实临时目录正常删除断言有效；active 未覆盖的问题由本评审发现，并未因已有专项通过而关闭。
4. `test_local_scope_v2.py` 独立读取完整历史冻结键，逐项计算 expected/actual SHA256 并比对 records 与 gate，另有真实临时文件匹配/修改/缺失三态。冻结数值未回写；软件测试验证真实阻断报告，不要求当前生产代码假装匹配历史身份。
5. 独立 `docs/testing/check_research_freeze.py` 实跑退出码 1：15 项中 6 项漂移（rag_query、models、retrieval、generator、doc_processor、uv.lock），status=DRIFT_REQUIRES_REVIEW，research_execution_authorized=false。研究仍 BLOCKED；没有科学通过、实际模型或实验可复用结论。该脚本是独立准入检查，不宣称已经接入可信 CI/分支保护。

## 独立验证

环境：`.tmp/backend-quality-venv-20261012/Scripts/python.exe`，`-B`，PYTHON_DOTENV_DISABLED=1、HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1、PYTHONDONTWRITEBYTECODE=1。未调用真实供应商或模型。

| 命令范围 | 结果与实际限制 |
|---|---|
| `-m pytest backend/tests/test_table_security_readiness.py backend/tests/test_guard_readiness.py backend/tests/test_service_readiness.py backend/tests/test_local_scope_v2.py -q --basetemp backend/tests/_sandbox_tmp/review-readiness-20261013-01` | 沙箱内 exit1，asyncio socketpair accept 超时；不能算通过。 |
| 同组合，basetemp `review-readiness-20261013-02`，获准沙箱外 | 121 passed / 12.11s，exit0。 |
| `-m pytest backend/tests/test_isolated_guard.py backend/tests/test_isolated_guard_v2.py -q --basetemp backend/tests/_sandbox_tmp/review-guard-real-20261013-01` | 沙箱内 24 passed / 1 failed，硬链接夹具 WinError5，exit1。 |
| 同 child guard 组合，basetemp `review-guard-real-20261013-02`，获准沙箱外 | 25 passed / 3.02s，exit0。 |
| `-B docs/testing/check_research_freeze.py` | exit1，真实研究漂移，必须保留阻断。 |
| 临时目录 active_version=0 复现、受限 256/1024/2048 谓词及 `2**63` limit 探测 | exit0 表示探测成功执行；输出明确复现上述缺陷，不是功能通过。 |

首轮审查快照 SHA256：

```text
backend/table_index.py a0f700cf31d9110d92a2b60e5f07c036ac46d0c57a4b215c7f98cdb6709d9a0a
backend/services/lifecycle.py f782a4c2f75e7de7b4a87d7779ee098c97f867bed5b6aa16554bb2b3b65964d1
backend/tests/test_guard_readiness.py d064ff9e41b98c986fbd289d39fc285bbe116b3703afca7909ed25707ad92814
backend/tests/test_table_security_readiness.py 04f06662ac15a6fabc4147b8e1aee16230cc8b9ed037b82372847851978c6777
backend/tests/test_local_scope_v2.py 8512d161b404683ef71750c28afe50008e9bef41bcffc3bab8766ed8aa83977d
backend/tests/test_service_readiness.py a5b057616dd6af260eba02ab117d3f646b245bdf7e234ee2f3bd1915aab8668c
docs/testing/check_research_freeze.py 44045a3fa3cfd53876dd628dd1328dcb31b7d5b081b87d73c0600a94c41d8e3f
```

## 优化建议汇总

1. 先修 active 永不删除与异常元数据拒删，补回滚真实行为测试并独立复核消费者。
2. 补总谓词和 limit 范围，复验正常 EAV/宽表/异常行为及资源界。
3. 最终快照重新执行适用专项、固定完整生产范围的全量双覆盖率及漏洞扫描；此报告不替代这些门槛。保留研究独立 gate 的非零阻断，没有 commit/push/deploy。

## 追加复核：查询资源界关闭、嵌入式向量拓扑

协调者针对本评审反馈新增 `top_k` 严格 int 0..1000、conditions 严格 list 1..32。独立复读检查与 `test_table_security_readiness.py + test_embedded_vector_readiness.py` 组合实际 **51 passed / 5.39s、exit0**，basetemp=`backend/tests/_sandbox_tmp/review-table-vector-20261013-01`，同上述离线环境。1001、2**63、33 谓词新增拒绝断言有效，Medium 关闭；生命周期 High 仍开放，等待修复后的独立验证。

`test_embedded_vector_readiness.py` 四项独立检查含 YAML/AST 拓扑契约和真实 PersistentClient；真实测试保存两条显式向量、source 过滤、在新解释器读取持久化、按 source/id 删除，旧 CHROMADB_HOST/PORT 环境变量不能把该 adapter 重定向到 HTTP。源码固定 collection metadata 仅 hnsw:space/dimension，调用没有接收用户 embedding configuration/trust_remote_code；静态检查仅作为契约防漂移，真实跨进程行为补足运行证据。

核查当前 compose/CI：已移除独立 Chroma HTTP 服务、依赖及 host/port 配置，保留后端 `graphrag_data:/app/output`。没有部署、删除既存 volume 或宣称存量服务已停机。依赖 audit 命令仍保留 Chroma 公告，不 ignore；CI 中“compose still contains a server”解释注释需要回流为当前拓扑。

对当前 Chroma 1.5.9，独立查阅安装源码 `chromadb/api/collection_configuration.py` 与 `chromadb/server/fastapi/__init__.py`，并在线核对四份官方 GitHub Reviewed Advisory：

- [GHSA-f4j7-r4q5-qw2c](https://github.com/advisories/GHSA-f4j7-r4q5-qw2c)：恶意模型库与 trust_remote_code 通过 Chroma 创建 collection HTTP 端点进入代码加载。
- [GHSA-36p7-vc44-83pf](https://github.com/advisories/GHSA-36p7-vc44-83pf)：具有 UPDATE_COLLECTION 权限的对应更新代码加载路径。
- [GHSA-xph7-9rjv-w5fr](https://github.com/advisories/GHSA-xph7-9rjv-w5fr)：Chroma SimpleRBAC provider 租户/数据库/collection 边界缺失。
- [GHSA-2wm9-hf6c-p5cr](https://github.com/advisories/GHSA-2wm9-hf6c-p5cr)：Chroma 认证用户的跨租户 collection 授权缺失。

这些公告当前仍无 patched version。基于公告前提和当前固定 adapter/配置的推断：默认应用入口没有发现可达上述 HTTP/RBAC 或任意模型配置的路径，移除闲置服务是实际减少攻击面；不能把受影响包说成已修复或安全扫描清零。未来引入 Chroma HTTP server、用户可控 collection 配置、embedding function 或不可信持久化数据库必须重新评估。镜像与真实部署未验证，pip-audit 非零仍是当前阻断。

追加复核快照：

```text
backend/table_index.py fa9ff038fe21ad71597982a15afa0137a9dd6072f7c57b25f610b77bfd620297
backend/tests/test_table_security_readiness.py 0a60afa1aff0bdd4ce921468fd28473d3f31568c584ef47c165884b5e93ee6a8
backend/tests/test_embedded_vector_readiness.py 75266308dadf9ee3d6f09972c1786d32332da8899ff41f2e64e25b3a400e672e
docker-compose.yml dee79471ff5da4bbf38db73af48ce588a66351cdb3a05cb779e2428d13ee7db2
.github/workflows/ci.yml 5f6a4c578b3f3f786c95002be2f6e85839f4c2cb6a8e836c19f03866e34a193d
```

当前统计：High 1 开放，Medium 1 已关闭，Critical/Low 0。本报告的测试组合存在重叠，不能相加为全量测试数。接续由协调者记录 memory；本子任务不写其所有的记忆或产品文件。
