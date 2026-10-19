# R8 Phase 1 消费者独立审查

审查总结：分页共用入口、单遍 BM25 分词及 TableIndex 选择规则在本次合成真实依赖范围正确，原作者 20 例独立复跑全部通过。新增 9 例发现 2 项 Medium（3 个失败用例），本冻结版本尚不能关闭消费者专项；Critical 0、High 0、Medium 2、Low 0。

审查输入：根 AGENTS、memory/index 与 2026-10-16 记录、同日 SQLite adapter 设计和计划、消费者测试报告。评审仅 Phase 1，不审候选 adapter 组合。分支 master，工作树已有大量他人修改；仅写私有评审目录和本报告。

## 🟡 Medium

### 1. 首次取值和空输入早退绕过 close

文件：冻结 `source/backend/index_registry.py`，行 214–218、229–235。

`next(iterator)` 位于清理 finally 外。可关闭迭代器在首次 next 抛出 RuntimeError 或 StopIteration 时均未 close，违反明确的正常耗尽、异常主动释放合同。三个新入口外层 finally 会关闭它们自己的 chunk generator，因此这不是三个入口已证明存在的 SQLite 连接泄漏；但共享构建函数直接接收持有资源的可关闭 iterator 时留下资源，独立新例证明该分支缺口。

建议：在成功导入 rank 后创建 iterator，把首次 next、空返回、BM25 构建全部放在同一个 try/finally 中。ImportError 分支须保留未消费 chunks 给调用方 TableIndex fallback，不应为了此修复关闭尚需消费的输入。

Before：

```python
iterator = iter(chunks)
try:
    first = next(iterator)
except StopIteration:
    return None
# ...
try:
    return (BM25Okapi(tokens()), retained)
finally:
    iterator.close()
```

After（结构示例）：

```python
iterator = iter(chunks)
try:
    try:
        first = next(iterator)
    except StopIteration:
        return None
    # Define retained and tokens here.
    return (BM25Okapi(tokens()), retained)
finally:
    close = getattr(iterator, 'close', None)
    if close is not None:
        close()
```

独立失败：`test_first_read_always_closes[exc0]` 与 `[exc1]`，期望 closed 为 True，实际 False。

### 2. rag helper 丢失无能力对象的 None 回退

文件：冻结 `source/backend/routes/rag_query.py`，行 36–44；抛错位置 `paged_chunks.py:11`。

原 helper 在对象没有 `_collection` 时返回 None；现在只检查 None，传入既无分页能力又无旧 collection 能力的对象会抛 AttributeError。应允许仅具备新分页接口的对象，同时保留二者均缺失时的旧回退。

Before：

```python
if vector_store is None:
    return None
```

After：

```python
if vector_store is None or (
    not callable(getattr(vector_store, 'iter_record_pages', None))
    and not hasattr(vector_store, '_collection')
):
    return None
```

独立失败：`test_rag_no_capabilities_preserves_none`。独立 `test_rag_page_only_supported` 已通过，修复须保留新接口支持。

## 验证与证据

独占 `.tmp/sqlite-r8-consumers-review-20261016/`，从冻结 source 完整复制，再只新增 `source/backend/tests/test_independent_edges.py`。未修改冻结、生产、环境和密钥。66 项冻结 manifest hash 全部核验一致，私有既有 source 逐文件一致；核验命令 `D:/graghRAG-agent/.tmp/backend-quality-venv-20261012/Scripts/python.exe -B -X utf8 .tmp/sqlite-r8-consumers-review-20261016/verify.py` exit 0。冻结 manifest SHA256：`eb7352e09e129dc5c7b703b45a827aa3d82d5d000f954fc80b992152be360230`。

实际测试命令：

```text
D:/graghRAG-agent/.tmp/backend-quality-venv-20261012/Scripts/python.exe -B -X utf8 -m pytest .tmp/sqlite-r8-consumers-review-20261016/source/backend/tests/test_r8_paged_consumers.py .tmp/sqlite-r8-consumers-review-20261016/source/backend/tests/test_independent_edges.py -q -p no:cacheprovider
```

pytest exit **1**，`3 failed, 26 passed in 5.80s`。外层 PowerShell打印退出码并完成，shell exit 0 不代表 pytest 成功。日志 `review.log`，机器回执 `receipt.json`，记录准确命令、退出码、各修改源文件及新增测试/日志 SHA256。

独立新增 9 例：首次异常及空耗尽 close（2 失败）、无能力 rag 回退（1 失败）、page-only 对象（1 通过）、缺 rank 的 build/eval × 有/无 table（4 通过）、页面错列异常 close（1 通过）。后四种缺 rank 组合验证 TableIndex 输入包含完整全部记录或唯一末页 table，未丢数据。

源码核查：`build_indices.main()` 使用同一构建函数且有 main guard；`run_evaluation.main()` 委托 `build_optional_indices()`；rag helper 直接共用 `iter_store_chunks`。BM25 保留最终 chunks 并向真实 rank_bm25 0.2.2 传无 tokenizer 参数的 token generator，无完整 tokenized 暂存；原 20 例中逐元素 scores 与旧 token 算法一致。真实 SQLite WAL snapshot、末页 137/17、并发写删、分词异常 close、DuckDB ingest 观察均独立复跑通过。

legacy Chroma 单次全量 get fallback **未转为 snapshot 分页**。此分支及最终 BM25/chunks/TableIndex/persist JSON 仍 O(N)，不声称全 runtime 有界内存、严格 RSS 上限或 Chroma 全域一致性。candidate adapter 合并、provider 全链、全量 backend/双90覆盖、安全扫描未执行；不能作为提交或生产准入。

## 优先级与接续

1. 在新 revision 修复上述两项；保持原 66 项冻结不动。
2. 在修订私有副本复跑原 20 例及本次 9 例，核最终 source hash，再判断专项是否闭环。
3. 候选 adapter 与消费者另建组合目录运行真实组合及后续全量门槛。本报告不预测修订结果。

本轮未提交、推送、部署。memory 由 root 汇总，避免越过评审文件所有权。
