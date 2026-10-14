# 2026-10-13 Readiness 独立复审

## 审查总结

本轮独立复跑与静态审查支持 widget 文本安全、上传异步生命周期、跨组织归档保护、KG 高水位严格类型、索引导出失败保留及测试临时路径整改。另发现飞书回调配置校验后缺签名仍放行的既有 High，已反馈并经独立责任人修复；最终独立四组111项通过，受影响Bot/Client/测试前后hash一致，按本次本地范围关闭该发现。不能据本报告宣称全项目完成或允许提交。

问题统计：首次审查 Critical 0、High 1、Medium 0、Low 0；最终新增High已关闭1、该审查范围开放阻断0。以下结论仅覆盖指定整改和实际执行范围；最终全量、漏洞、研究冻结、Docker/供应商及 CI 门禁由根报告分别核验。

## 输入与边界

- 已读取根 AGENTS.md、memory/index.md、memory/2026-10-13.md、测试规范及受影响前后端有效契约。分支 master，HEAD `46b202c3e400741fd569f024412c0745f224a538`；存在其他任务大量未提交变动，未清理或回退。
- 独立上下文 reviewer，仅拥有本报告；未改产品、测试、真实 output 或 `.env`，未调用 provider。使用 verification-before-completion 的实际证据检查；using-superpowers 对已派发子 Agent 明确要求跳过其启动协议。
- 后端真实执行 JWT/JSON持久化/ASGI/DuckDB/BM25/解析依赖；OIDC/飞书 outbound HTTP 为边界替代，不冒充供应商集成。TestClient 通过正常 `require_escalated` 自动审批执行。
- 独占 basetemp：`backend/tests/_sandbox_tmp/review-final-20261013`。既有 sandbox_tmp_path 夹具另在测试目录生成 UUID 临时目录并清理；未改夹具或全局默认输出路径。

## 问题清单

### 🟠 High — 配置飞书校验后缺失签名头仍可处理事件（初始发现，已追加闭环）

位置：`backend/routes/bot.py:34-41`；原测试 `backend/tests/test_auth_tenant_readiness.py` 的 `test_bot_signature_verification`。

配置 `FEISHU_VERIFICATION_TOKEN` 时，只有 timestamp/nonce/signature 全部存在才进入校验，缺任一项直接跳过。测试对 missing 明确断言 200，只证明当前行为，不能证明鉴权正确。非 challenge 的真实事件仍可进入 BotHandler，可能写反馈或触发查询/外发；因此属于权限边界风险。此问题为既有逻辑，并非 build_error_card 参数修复引入。

建议：校验配置存在时，缺任一必需签名头即返回 401；签名错误保持拒绝。测试参数化缺全部及分别缺三个头，以 handler 不调用断言拒绝发生在业务副作用之前。

```python
# before
if timestamp and nonce and signature:
    if not client.verify_signature(timestamp, nonce, body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

# suggested after (以责任人最终实现/复跑为准)
if not (timestamp and nonce and signature):
    raise HTTPException(status_code=401, detail="Missing signature")
if not client.verify_signature(timestamp, nonce, body, signature):
    raise HTTPException(status_code=403, detail="Invalid signature")
```

已及时通知根协调者，不自行改责任人的产品或测试文件。

## 指定整改与行为质量核查

| 项目 | 独立核查 |
|---|---|
| Widget XSS | `createElement` 通用字符串 children 为 textContent；Markdown 在 HTML结构生成前转义。真实 shipped IIFE 测试分别断言恶意 title/answer/label/type 的可见文本及不存在 img/onerror；错误消息、用户消息同样有文本断言。静态 HTML仅 loading 占位，不依赖单纯搜索源码证明安全。 |
| Upload 晚回调 | effect cleanup active=false；响应前检查 store 当前 taskId/status；inFlight 防重入。ingest 使用 generation、mounted、file/task 身份保护。deferred Promise 测试覆盖 unmount/新任务/reset/重复提交的成功与失败，并断言共享 store、轮询调用次数及恢复，不只断言函数被调用。 |
| 跨组织 archive | 归档前读取项目并比较 org_id，匹配失败404；测试以自身组织org_admin访问另一组织project，并确认 is_archived仍False；已有本组织成功归档及缺资源/权限矩阵仍执行。 |
| 飞书错误卡片 | build_error_card 使用其支持的 message 参数；真实卡片代码执行，断言 alert title/content/fallback及最大5条外发数；HTTP边界替代，有成功和connection failure场景。该局部修复不代表整个Bot鉴权完成，见High。 |
| KG strict highwater | `type(highwater) is int` 排除bool/float，正整数限制排除0/负数；版本列表同样拒绝bool及非法类型。7种错误输入测试同时验证create抛错、清理返回0、元数据bytes不变、12个目录保持且无retired目录；不是仅assert raises。无高水位字段的旧清单按历史兼容默认值并结合清单/磁盘max递增。 |
| 索引失败与全量导出 | export_rows异常返回None且不调用覆盖；真实TableIndex与RestoredTableIndex显式完整export，不受交互query上限约束。独立6001行实测验证持久化及恢复全部行；export_rows抛错后bytes保持。旧query-only fallback保留兼容行为，本报告不将其称为任意第三方适配器完整导出保证。 |
| 测试路径隔离 | autouse同时设置环境变量与registry路径；reload后重新从环境取临时root。现有测试核对真实table_artifact前后hash，并在临时root落盘。此fixture只隔离BM25/table默认产物，不声称覆盖所有服务持久化路径；API专项另单独patch用户/租户/audit/key目录。 |

## 实际独立验证

时间：2026-10-13，Node专项实际起始20:17:44（Asia/Shanghai）。Python使用隔离 `.tmp/backend-quality-venv-20261012/Scripts/python.exe`，没有重新安装或修改环境。

1. 在 backend 执行：

   ```powershell
   $env:PYTHONDONTWRITEBYTECODE='1'
   & ..\.tmp\backend-quality-venv-20261012\Scripts\python.exe -m pytest tests/test_auth_tenant_readiness.py tests/test_kg_highwater_validation.py tests/test_runtime_artifact_isolation.py tests/test_parser_index_readiness.py -q -p no:cacheprovider --basetemp=tests/_sandbox_tmp/review-final-20261013
   ```

   实际 **74 passed、1 warning、7.98s，最终进程exit0**。工具先返回session7091，随后write_stdin确认最终exit0；没有用测试摘要替代进程退出码。警告为Starlette中anyio BlockingPortal alias deprecated。此为签名修复前的专项结果，修复后必须再复跑。

2. 在 frontend，PATH前置仓库隔离Node22运行：

   ```powershell
   $env:PATH='D:\graghRAG-agent\.tmp\node22-runtime\node-v22.23.3-win-x64;' + $env:PATH
   pnpm.cmd exec vitest run tests/widget.test.ts tests/upload-races.test.tsx
   ```

   实际 **2 files / 18 passed / 3.94s，exit0**。只复跑相关行为；完整122测试覆盖报告单独核对如下，不混称独立重新执行全前端coverage。

3. 独立 Python 读取53项input-manifest，逐项计算当前SHA256；枚举src的ts/tsx和public的js，按配置排除测试本身；与coverage-summary逐文件集合比较。

   **exit0，53 inputs drift=[]，expected生产29、报告29、missing=[]、extra=[]**。manifest原文件SHA256 `88e7356ceefccf79fa1fb9b8f11110cb11b66ea8d41faab2c5a3cc0182a0356d`。首次探针未剔除 `src/lib/queryContract.test.ts` 而得到30/29、exit1；核对其为测试且在配置明确排除后纠正生产集合复跑，未改产品范围/配置或覆盖报告。

   原始行 **927/957=96.8652037618%**，分支 **853/913=93.4282584885%**；两项均以原始计数超过90%。coverage日志与JSON计数一致；dist/chat-widget.js与public源bytes完全相同。覆盖文件集合包含未导入入口/类型文件，测试文件排除合理，未发现缩分母或ignore新增。

4. 独立真实DuckDB规模/恢复/异常探针（根目录使用上述Python `-` 执行stdin）：

   ```python
   import sys, pathlib, tempfile, json
   r = pathlib.Path.cwd()
   sys.path.insert(0, str(r / 'backend'))
   from table_index import TableIndex
   import index_registry as ir
   with tempfile.TemporaryDirectory(dir=r/'backend/tests/_sandbox_tmp/review-final-20261013') as tmp:
       t = TableIndex()
       rows = [(str(n),'s','sheet',n,'value',str(n),float(n),'','{}') for n in range(6001)]
       t.conn.executemany('INSERT INTO table_rows (row_id,source_file,sheet_name,row_number,column_name,column_value,column_value_numeric,unit,context_json) VALUES (?,?,?,?,?,?,?,?,?)', rows)
       p = pathlib.Path(tmp) / 'table.json'
       ir.snapshot_table_index(path=p, index=t)
       v = json.loads(p.read_text(encoding='utf-8'))
       assert len(v['rows']) == 6001 and v['rows'][-1]['row_number'] == 6000
       before = p.read_bytes()
       class Broken:
           def export_rows(self):
               raise OSError('independent read failure')
       assert ir.snapshot_table_index(path=p, index=Broken()) is None
       assert p.read_bytes() == before
       assert len(ir._deserialize_table_index(v).export_rows()) == 6001
       t.conn.close()
   ```

   **exit0：6001行持久化/恢复、导出异常旧bytes保留全部通过**。首次探针遗漏必填row_id导致ConstraintException/exit1，补齐真实schema字段后成功；没有修改产品schema或忽略错误。临时目录自动清理。

## 快照定位

以下为本轮复核读取后的SHA256；Bot及其测试正在由责任人处理签名High，须以追加复核hash为最终身份。

| 文件 | SHA256 |
|---|---|
| backend/kg_store.py | 364ace85621aa64f06a934d0524da30fb695cecb4e91199b2f07fc013d7a08cd |
| backend/index_registry.py | 4406c4234a262b099447751d3f7b3ea3c441a49f28934045eb4ad8d978262b93 |
| backend/tests/conftest.py | b4883b1f062ffc59d30aeb26803a88f308573dd66a14db7f49398022c97a9539 |
| backend/routes/tenants.py | ebb522f2d883d89655c23104290ed3c84a6994dab4eae594ae79ea468f9c468f |
| backend/routes/bot.py（修复前） | b0ed91c1789ee4dd3a38c5f82bc0b77f9c56c01389333d7ad52d711cd55ee922 |
| backend/tests/test_auth_tenant_readiness.py（修复前） | c6f0f039367916ac3f70feb0b4f36824700ab59de808da41ae6f06be594be625 |
| frontend/public/chat-widget.js | 1c5600bfa3264bd316c6dbcc034decf49b264737de218be96dfed827d7372055 |
| frontend/src/pages/UploadPage.tsx | 50e3c5077f7710752b1ea5e507904b8acf3a6e3842d1062b24dbe8fc1a5e33ce |

## 优化建议汇总与限制

1. 优先闭合签名High，并独立重跑覆盖missing/partial/invalid/valid四类、handler拒绝副作用断言；随后根协调者以最终产品快照重跑全量和覆盖，旧全量不沿用。
2. 保留供应链未修公告、研究冻结漂移、真实供应商/部署/可信CI未执行的独立阻塞；局部与前端双90不代替这些门槛。
3. 接续memory由根协调者统一更新，避免与其他Agent同时编辑；本reviewer未commit/push/deploy。Windows仍audit-only-windows。

## 签名整改接续及最终复核

责任人扩大受影响范围至 `backend/services/feishu_client.py`，以 Encrypt Key 参与 `SHA256(timestamp + nonce + encrypt_key + 原始body bytes)`，使用constant-time比较；只有Verification Token的部署改为校验v1 body.token / v2 header.token。顶层URL验证也移到对应鉴权之后，避免challenge路径绕过。该方案解决原始发现的未认证事件放行，并纠正把Verification Token误作签名密钥的旧逻辑；原始建议示例不是实际完整协议。

独立静态复核新增参数化测试：7种缺头组合×顶层/事件URL验证，401且真实handler观察器calls=[]、outbound=[]；token-only三类token×v1/v2×顶层/事件验证；原始非UTF8 bytes、错误密钥、改body/nonce/timestamp的签名失败。未调用真实飞书。

第一次复跑相同后端四组命令：**102passed/1warning/8.04s，最终exit0**；但测试文件执行前后hash从 `11f18ff1b126088f89215ac359365c9eec27a97edd00206922d5ab87c7925fbf` 变为 `cb72cf458f7713b2b61bb2318775f7837fffa57ab8cd7f2c21d610e1330dad42`（责任人补测顶层签名验证），因此该次明确不能作为最终冻结快照证据。Bot和client前后hash相同；已通知协调者等待停止修改后重跑。

随后对稳定输入再执行相同四组命令，实际 **111passed / 1warning / 8.54s，最终进程exit0**（工具session33865后write_stdin确认）。本次执行前后三个受影响文件SHA256完全一致：

| 最终输入 | SHA256 |
|---|---|
| backend/routes/bot.py | 57961698ea43158ac8d88457707dd63b8a886fff551b16f86f42c91ce6296869 |
| backend/services/feishu_client.py | 01e4c99d3f34ff478ba51dc806828c36a701452efd524a8bcfe9fdedc114a994 |
| backend/tests/test_auth_tenant_readiness.py | cb72cf458f7713b2b61bb2318775f7837fffa57ab8cd7f2c21d610e1330dad42 |

独立结论：该High在本次本地受影响范围关闭。token-only模式正确匹配token可放行，encrypt_key模式拒绝缺任一签名头；拒绝发生在真实事件分发之前，顶层challenge也经过鉴权。未声明实现encrypted payload解密、重放治理或真实飞书供应商验收，这些不在本次最小修复证据内。最终全量/覆盖与有效规范回流由根协调者收口，随后若产品或测试变化，应重跑对应检查。

