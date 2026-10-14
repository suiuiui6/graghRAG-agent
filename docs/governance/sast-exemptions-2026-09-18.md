# 静态安全扫描（SAST）豁免记录

2026-10-13状态更新：下方为历史记录，B608豁免已撤销。真实DuckDB安全回归后，条件改为有界token语法编译表达式、limit精确整数校验；不得将LLM输出视为可信。固定90生产文件Bandit1.9.4全规则扫描中危0/高危0/低危136、errors0/nosec0/skipped_tests0，完整扫描exit1（低危发现仍存在），见`docs/testing/2026-10-13-to90-wave3-bandit.json`。CI命令已移除`--skip B608`，但远程CI未执行，Windows仍audit-only-windows；不能据本地结果声称保护分支有效。历史数量和旧命令不代表当前状态。

> **日期**：2026-09-18
> **范围**：`backend/` 全量 Python 源码（`.venv` / `output` / `uploads` / `tests` 已排除）
> **工具**：`uv tool run bandit==1.7.10`（CI 中钉版本）
> **CI 落地**：`.github/workflows/ci.yml` 的 `bandit-sast` job
> **体例**：沿用 `docs/governance/dependency-audit-2026-09-17.md`

---

## 一、扫描口径

```
uv tool run bandit==1.7.10 -c pyproject.toml -r . -ll -ii --skip B608
```

- `-c pyproject.toml`：**必须带**。bandit 只有通过 `-c` 才会读 `[tool.bandit].exclude_dirs`，
  否则会把 `.venv` 下 1.9 万个文件一起扫（本地实测：漏掉 `-c` 会直接卡住）。
- `-ll -ii`：中危 + 中置信度起阻断。默认 `-l -i` 会报大量低危噪声，
  结果是阻塞 CI 或被迫整体跳过 —— 二者都会训练人忽略该 job。
- 实测扫描量：18,011 行代码，`#nosec` 0 处。

---

## 二、本轮已修复的真问题

### B202 `tarfile_unsafe_members` —— 高危/高置信度，**已修**

`services/backup.py:240` 的 `tar.extractall(path=self.base_dir)` 无成员校验。
恶意或损坏的备份包可通过 `..` 路径穿越或符号链接写到目标目录之外。

**修法**：加 `filter="data"`（Python 3.12 起支持，本项目实测 3.12.8 可用），
拒绝绝对路径、`..` 穿越、指向基目录外的符号链接与设备文件。

---

## 三、豁免项

### B608 `hardcoded_sql_expressions`

**命中**：`table_index.py:237`（1 处，中危/中置信度）

**代码**：
```python
where = " AND ".join(f"({c})" for c in conditions)
sql = f'SELECT *, \'{table_name}\' as _source FROM "{table_name}" WHERE {where} LIMIT {top_k}'
rows = self.conn.execute(sql).fetchall()
```

**可利用性判定 —— 部分成立，但不是教科书式注入**：

| 拼接项 | 来源 | 是否受控 |
|---|---|---|
| `table_name` | `self._wide_tables_created`，创建时经 `_sanitize_name()` | ✅ 否。`re.sub(r'[^\w]', '_', name)` 会剥掉引号、分号、连字符，无法闭合标识符 |
| `top_k` | 调用方传入的 int | ✅ 否 |
| `where` / `conditions` | `retrieval.py:379` 从**预处理结果**读 `table_conditions`；该字段由 LLM（`retrieval.py:94` "if intent is metric, extract numerical conditions"）产出 | ⚠️ **是** |

**结论**：与同文件 `:226-229` 的 DDL 路径不同 —— 那一路已用 `_sanitize_name`，
而 `:246` 的 WHERE 子句是**直接拼接、未做任何转义或白名单**。攻击面是
「LLM 产出被污染的 `table_conditions`」而非用户直传 SQL，属**注入类别成立、
严重度低于典型 SQLi**。

**为什么本轮不修**：正确解法是把 `table_conditions` 从「自由文本表达式」改为
结构化条件对象（列名白名单 + 运算符枚举 + 参数化值），这要同步改
`retrieval.py` 的抽取 prompt 与 `index_registry.query` 的签名 ——
属跨模块改造，不应在日志/异常治理（F003/F004）里顺手做，见
`.lra/feature-list.json` 的独立待办。

**复查触发条件**（任一满足即须重新评估并优先处理）：
1. `table_conditions` 的来源改为**任何用户可直接提交**的入口（当前仅 LLM 产出）
2. `retrieval.py` 的预处理 prompt 变更，使 `table_conditions` 可含引号/注释符
3. `table_index.py` 的查询路径新增除 `_query_wide_tables` 之外的拼接点
4. 引入多租户后，条件表达式可跨租户构造

---

## 四、低于 CI 门槛的发现（**未豁免，仅记录，不阻断**）

`-ll -ii` 门槛之下的项不会被扫描，但为避免"看不见就以为没有"，此处留档。
若将来放宽门槛至 `-l -i`，以下会浮现：

| 规则 | 数量 | 性质判定 |
|---|---|---|
| `B110 try_except_pass` | 113 | **已在源码内逐处标注理由**（`# noqa: S110, BLE001  # <理由>`），由 ruff 的 S110 规则持续守卫。真正的审计在源码注释里，不在本文件重复 |
| `B603/B607 subprocess` | 9 + 9 | `worker.py` 用 `subprocess.run(["curl", ...])`（该环境屏蔽了 Python requests）。argv 为**静态列表**、无 `shell=True`、插值项来自 env 与 MinerU 响应，不接受用户直传 shell 元字符。计划初稿预期它会被命中，实测加固后不阻断 |
| `B404 blacklist` | 4 | 仅为 `import subprocess` 本身（`errors.py:10`、`pipeline.py:62,149`、`worker.py:18`），无行为含义 |
| `B112 try_except_continue` | 1 | `table_index.py:260`，已标注理由 |
| `B106 hardcoded_password_funcarg` | 3 | **误报**：`services/auth_service.py:112,135,154` 的 `token_type="Bearer"` —— 这是 OAuth 的 token **类型**字段，不是密钥 |

---

## 五、复审安排

- 每次 CI 运行 `bandit-sast` job 即为一次自动复审
- 豁免仅 1 条（B608），其复查触发条件见第三节
- 新增豁免必须：① 写入本文件并给出可利用性判定与触发条件；
  ② 在 `.github/workflows/ci.yml` 的 `--skip` 处附注释说明，二者缺一不可
