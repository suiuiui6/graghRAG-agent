# 供应链治理（F001+F002）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 backend 依赖从"能装但不完整、无锁定"变为"可复现安装 + 有供应链安全门禁"。

**Architecture:** 在 `backend/` 建立 `pyproject.toml`（声明真实依赖，含代码已 import 但缺失的 `oss2`）+ `uv.lock`（锁定版本）；`langextract` 作为本地路径依赖（editable，指向仓库内 `langextract/`）；新增 `scripts/check_imports.py` 做干净环境导入冒烟；CI 增加 dependency-audit / secret-scan / 导入冒烟三个门禁。

**Tech Stack:** uv 0.11、Python 3.12、pytest、pip-audit、bandit、detect-secrets、GitHub Actions

---

## 背景事实（已侦察确认，勿再猜测）

| 事实 | 证据 |
|------|------|
| `oss2` 被代码 import 但不在 requirements | `backend/oss_uploader.py:5` `import oss2` |
| `langextract` 是**本地子模块**，非 pip 包 | `backend/pipeline.py:35` `sys.path.insert(0, "../langextract")`；`langextract/pyproject.toml` 存在 |
| `aiofiles` 在 requirements 但**零引用** | 全项目 grep `aiofiles` 无命中 |
| backend 无 `pyproject.toml` / 无锁文件 | `find` 仅命中 `developer-kit/` 与 `langextract/` |
| `backend/.venv` = Python 3.12.8，uv 0.11.16 可用 | `backend/.venv/Scripts/python.exe --version` |
| CI 现有 lint / test / docker 三 job，**无安全扫描** | `.github/workflows/ci.yml` |
| `.gitignore` 已忽略 `.env` / `.venv/` / `__pycache__` | `.gitignore:2,8,14` |

**重要约束**：`langextract` 不能写成 `langextract>=x.y`（PyPI 上无此包），必须用 `[tool.uv.sources]` 指本地路径。

**镜像决策（2026-09-17 与项目负责人确认）**：`backend/uv.lock` 生成时绑定了阿里云镜像（`--default-index https://mirrors.aliyun.com/pypi/simple/`），锁文件中 205 个包全部记录该 registry URL。**决策：保留阿里云锁文件**，理由是本机到 pypi.org 连通性差（实测单次解析 1m18s 至超时），且项目本就以国内镜像为基线。

**该决策的直接后果（已实测，含两阶段验证）**：

锁文件把**索引与下载 URL 都写死**为阿里云（794 个 wheel + 976 个 URL 条目，`files.pythonhosted.org` 出现 0 次）。因此：

| 场景 | 结果 |
|------|------|
| `uv lock --check`（不带参数 / 指向阿里云） | exit=0 ✓ |
| `uv lock --check --default-index https://pypi.org/simple/` | **exit=1**（"lockfile needs to be updated"）✗ |
| 本机 `uv sync` → 下载 | 走锁内阿里云 URL，实测 HTTP 200 / 0.18s ✓ |

**关键机制（勿误判）**：`UV_DEFAULT_INDEX` 只影响*索引解析*（即 `uv lock` / `--check` 重解析时去哪查），**不影响*下载*** —— 下载 URL 是锁文件里写死的。所以：

- CI 里设 `UV_DEFAULT_INDEX=阿里云` 是为了让 `uv lock --check` 通过（否则它会去 pypi.org 重解析，导致 exit=1）
- 但**实际的包下载能不能成功，取决于 runner 能否访问 `mirrors.aliyun.com`**，与 `UV_DEFAULT_INDEX` 无关
- 若未来在无法访问阿里云的 runner 上跑 `uv sync --locked`，需要**重新生成一份指向该环境可达镜像的锁文件**，改环境变量是没用的

本机无 `UV_DEFAULT_INDEX`、无 `uv.toml`，`uv lock --check` 仍 exit=0（因为它按锁内记录的源解析），阿里云主机实测可达。

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `backend/pyproject.toml` | 声明依赖、锁定 Python 版本、配置 uv 本地源 | 新建 |
| `backend/uv.lock` | 锁定全部依赖版本 + 哈希 | 生成（uv lock） |
| `backend/requirements.txt` | 保留为运行依赖清单（兼容既有 Dockerfile/CI），与 pyproject 同步 | 修改 |
| `backend/scripts/check_imports.py` | 干净环境导入冒烟，校验关键模块可 import | 新建 |
| `backend/tests/test_supply_chain.py` | 测试：pyproject 与 requirements 一致、无幽灵依赖 | 新建 |
| `.pre-commit-config.yaml` | 本地提交前密钥扫描 | 新建 |
| `.github/workflows/ci.yml` | 新增 dependency-audit / secret-scan / import-smoke job | 修改 |

---

## Task 1: 建立 pyproject.toml 声明真实依赖

**Files:**
- Create: `backend/pyproject.toml`

- [ ] **Step 1: 写 pyproject.toml**

```toml
[project]
name = "graphrag-agent-backend"
version = "0.1.0"
description = "GraphRAG Agent 知识图谱问答系统后端（FastAPI）"
requires-python = ">=3.12,<3.13"

dependencies = [
    # Web 框架
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.10.0",
    "python-multipart>=0.0.18",
    # Agent / LLM 编排
    "langgraph>=1.0.0",
    "langchain>=1.2.0",
    "langchain-openai>=0.3.0",
    # RAG pipeline
    "chromadb>=0.5.0",
    "networkx>=3.0.0",
    "rank-bm25>=0.2.2",
    "sentence-transformers>=3.0.0",
    "python-docx>=1.1.0",
    "openpyxl>=3.1.0",
    # 基础设施
    "pyyaml>=6.0",
    "python-dotenv>=1.0.0",
    "requests>=2.32.0",
    "httpx>=0.27.0",
    "structlog>=25.0.0",
    "prometheus-client>=0.21.0",
    "apscheduler>=3.10.0",
    "pyjwt>=2.8.0",
    # 对象存储（代码已 import，此前漏声明）
    "oss2>=2.19.0",
    # 表格召回：table_index.py 缺包时 raise，但调用方
    # index_registry.build_table_index_from_chunks / worker.py 均 try/except 吞掉，
    # 缺失时表格召回静默失效、入库照常完成。列为默认安装，非硬必需。
    "duckdb>=1.0.0",
    # agentic_rag_mvp.py 直接 import，此前仅靠传递依赖
    "typing-extensions>=4.0.0",
    # 本地子模块：langextract（见下方 sources）
    "langextract",
]
# 刻意不声明（附理由，便于后续审计）：
#   jieba        —— index_registry.py:218 在 try/except ImportError 内，有 bigram fallback，软依赖
#   langchain-core —— routes/query.py:10 直接 import，但由 langchain / langgraph 硬性传递保证

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-timeout>=2.3.0",
    "pip-audit>=2.7.0",
    "bandit>=1.7.9",
    "detect-secrets>=1.5.0",
]

[tool.uv.sources]
langextract = { path = "../langextract", editable = true }

[tool.pytest.ini_options]
testpaths = ["tests"]
timeout = 60
```

- [ ] **Step 2: 验证 pyproject 语法合法**

Run: `cd backend && uv lock --help >/dev/null && python -c "import tomllib,pathlib; tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8')); print('TOML OK')"`
Expected: `TOML OK`

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml
git commit -m "build(backend): 新增 pyproject.toml 声明真实依赖，补 oss2 与本地 langextract 源"
```

---

## Task 2: 生成并提交 uv.lock

**Files:**
- Create: `backend/uv.lock`

- [ ] **Step 1: 生成锁文件**

Run: `cd backend && uv lock --default-index https://mirrors.aliyun.com/pypi/simple/`
Expected: 生成 `backend/uv.lock`，无报错

> **必须带 `--default-index` 阿里云镜像**：本机直连 pypi.org 会超时（实测 126.9s 后 5 次重试失败）。不带该参数会失败。
> **副作用**：uv 会把实际索引 URL 写进锁文件（205 个包，无"中性"写法）。这是已知且已接受的后果，见上文「镜像决策」。

> 若报 `langextract` 无法解析：确认 `../langextract/pyproject.toml` 存在且其 `[project].name == "langextract"`。这在侦察中已确认成立。

- [ ] **Step 2: 验证锁文件可复现安装**

Run: `cd backend && uv sync --locked --dry-run`
Expected: 输出将要安装的包列表，退出码 0，无 "lock file is out of date" 报错

- [ ] **Step 3: 确认锁文件已纳入版本控制**

Run: `git status --short backend/uv.lock`
Expected: 显示 `?? backend/uv.lock`（或 `A`），即未被 .gitignore 忽略

- [ ] **Step 4: Commit**

```bash
git add backend/uv.lock
git commit -m "build(backend): 生成 uv.lock 锁定依赖版本，杜绝构建漂移"
```

---

## Task 3: requirements.txt 与 pyproject 对齐

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 重写 requirements.txt（补 oss2/duckdb/typing-extensions，移除幽灵依赖 aiofiles）**

```
# 手写维护 —— 权威清单是 pyproject.toml，一致性由
# tests/test_supply_chain.py::test_requirements_matches_pyproject 强制。
# 改依赖请改 pyproject.toml 再同步本文件（勿直接跑 `uv export`，
# 那会生成含 `-e ../langextract` 的 1500 行全传递依赖清单）。
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
pydantic>=2.10.0
python-multipart>=0.0.18
langgraph>=1.0.0
langchain>=1.2.0
langchain-openai>=0.3.0
chromadb>=0.5.0
networkx>=3.0.0
rank-bm25>=0.2.2
sentence-transformers>=3.0.0
python-docx>=1.1.0
openpyxl>=3.1.0
pyyaml>=6.0
python-dotenv>=1.0.0
requests>=2.32.0
httpx>=0.27.0
structlog>=25.0.0
prometheus-client>=0.21.0
apscheduler>=3.10.0
pyjwt>=2.8.0
oss2>=2.19.0
# 选项依赖：table_index.py 缺包时会 raise，但调用方
# index_registry.build_table_index_from_chunks 与 worker.py 均 try/except 吞掉，
# 缺失时表格召回静默失效、入库照常完成。故此处为「默认安装」而非硬必需。
duckdb>=1.0.0
typing-extensions>=4.0.0
# 注意：langextract 为仓库内本地子模块（../langextract），
# 不通过 pip 安装，由 pipeline.py 的 sys.path.insert 注入。
# 刻意不声明：jieba（软依赖，有 fallback）、langchain-core（由 langchain/langgraph 传递保证）。
```

- [ ] **Step 2: 验证 requirements 可被 pip 解析（不实际安装）**

Run: `cd backend && pip install --dry-run -r requirements.txt 2>&1 | tail -5`
Expected: 能解析出包列表，不出现 "No matching distribution found for oss2"

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "fix(backend): requirements 补 oss2、移除零引用的 aiofiles，与 pyproject 对齐"
```

---

## Task 4: 导入冒烟脚本（TDD）

**Files:**
- Create: `backend/tests/test_supply_chain.py`
- Create: `backend/scripts/check_imports.py`

- [ ] **Step 1: 先写失败测试**

```python
# backend/tests/test_supply_chain.py
"""供应链治理回归测试：依赖清单一致性 + 关键模块可导入。"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND))

_PYPROJECT = _BACKEND / "pyproject.toml"
_REQUIREMENTS = _BACKEND / "requirements.txt"


def _normalize(name: str) -> str:
    """PEP 503 归一化：统一小写、下划线/点转连字符。"""
    return re.sub(r"[-_.]+", "-", name).lower()


def _pyproject_deps() -> set[str]:
    data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    deps = set()
    for raw in data["project"]["dependencies"]:
        # 取 "name" 或 "name[extra]" 或 "name>=1.0" 的名字部分
        name = re.split(r"[<>=\[;!,\s]", raw.strip(), maxsplit=1)[0]
        deps.add(_normalize(name))
    return deps


def _requirements_deps() -> set[str]:
    deps = set()
    for line in _REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = re.split(r"[<>=\[;!,\s]", line, maxsplit=1)[0]
        deps.add(_normalize(name))
    return deps


def test_oss2_declared_in_both():
    """oss2 被 oss_uploader.py import，必须在两处清单都声明。"""
    assert "oss2" in _pyproject_deps()
    assert "oss2" in _requirements_deps()


def test_no_ghost_dependency_aiofiles():
    """aiofiles 全项目零引用，不应出现在依赖清单里。"""
    assert "aiofiles" not in _pyproject_deps()
    assert "aiofiles" not in _requirements_deps()


def test_requirements_matches_pyproject():
    """requirements 与 pyproject 的依赖集合必须一致（langextract 除外，它是本地路径源）。"""
    py = _pyproject_deps() - {"langextract"}
    req = _requirements_deps()
    assert py == req, f"不一致 —— 仅 pyproject 有: {py - req}；仅 requirements 有: {req - py}"
```

- [ ] **Step 2: 运行测试，确认当前失败**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_supply_chain.py -v --tb=short`
Expected: `test_no_ghost_dependency_aiofiles` 与 `test_oss2_declared_in_both` FAIL —— 已实测确认：`aiofiles` 当前确实在 requirements.txt 中、`oss2` 确实缺失

> 说明：本 Task 的测试依赖 Task 3 已改完 requirements.txt。若按顺序执行到此处，Step 2 的这两个断言应已转绿；若单独执行本 Task，应看到上述失败——这正是 TDD 的红灯阶段。

- [ ] **Step 3: 写导入冒烟脚本**

```python
# backend/scripts/check_imports.py
"""干净环境导入冒烟：验证真实入库链路所需依赖齐全。

用法：python scripts/check_imports.py
退出码 0 = 全部可导入；1 = 有缺失。
"""
from __future__ import annotations

import sys

# (模块名, 用途说明) —— 覆盖真实入库链路，非演示链路
REQUIRED_MODULES = [
    ("fastapi", "Web 框架"),
    ("uvicorn", "ASGI 服务器"),
    ("pydantic", "请求/响应模型"),
    ("oss2", "OSS 对象存储上传（worker 真实入库必需）"),
    ("chromadb", "向量库"),
    ("networkx", "知识图谱"),
    ("sentence_transformers", "Embedding"),
    ("rank_bm25", "关键词检索"),
    ("docx", "Word 文档解析"),
    ("openpyxl", "Excel 文档解析"),
    ("duckdb", "表格召回 TableIndex（缺失时静默降级，不中断入库）"),
    ("structlog", "结构化日志"),
    ("jwt", "JWT 鉴权"),
    ("apscheduler", "定时任务"),
]


def main() -> int:
    missing: list[str] = []
    for mod, purpose in REQUIRED_MODULES:
        try:
            __import__(mod)
            print(f"  [OK]   {mod:<24} {purpose}")
        except Exception as exc:
            # 不只 ImportError：原生扩展（duckdb / sentence-transformers）
            # 缺失共享库时抛的是 OSError，只捕 ImportError 会漏掉并抛出难读的堆栈。
            print(f"  [FAIL] {mod:<24} {purpose}  —— {type(exc).__name__}: {exc}")
            missing.append(mod)

    if missing:
        print(f"\n缺失 {len(missing)} 个模块: {', '.join(missing)}")
        return 1
    print(f"\n全部 {len(REQUIRED_MODULES)} 个模块可导入。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_supply_chain.py -v --tb=short`
Expected: 3 passed（`test_critical_modules_importable` 已移出，导入校验统一由 `scripts/check_imports.py` 承担，避免重复）

- [ ] **Step 5: 运行冒烟脚本**

Run: `cd backend && .venv/Scripts/python.exe scripts/check_imports.py`
Expected: 所有行 `[OK]`，末行 `全部 14 个模块可导入。`，退出码 0

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_supply_chain.py backend/scripts/check_imports.py
git commit -m "test(backend): 新增供应链一致性回归测试与导入冒烟脚本"
```

---

## Task 4.5: 泛化「代码 import 未声明」检查（质量审查 I2 追加）

> **为何追加**：Task 4 的 `test_oss2_declared_in_both` 只是把 `oss2` 钉死为一个字符串字面量，`test_no_ghost_dependency_aiofiles` 只覆盖 aiofiles 一个包。质量审查做了变异测试，证明两者都是**同义反复**：新增一个幽灵依赖、或代码 import 了新包但两清单都没有，**三个测试全绿（漏检）**。而后者正是本计划的目标缺陷类型（`oss2` 被 import 却未声明）。本 Task 用 AST 扫描替换这两个测试。

**Files:**
- Modify: `backend/tests/test_supply_chain.py`

- [ ] **Step 1: 删除两个同义反复测试，替换为泛化检查**

从 `backend/tests/test_supply_chain.py` 中**删除** `test_oss2_declared_in_both` 与 `test_no_ghost_dependency_aiofiles` 两个函数，并追加以下内容（保留文件头部的 import 与 `_normalize` / `_pyproject_deps` / `_requirements_deps` / `test_requirements_matches_pyproject` 不变）：

在文件顶部 import 区补充：

```python
import ast
import importlib.metadata as importlib_metadata
```

在文件末尾追加：

```python
# ── 泛化检查：代码 import 的第三方包必须已在清单中声明 ──────────────────────
#
# 目的：捕获「代码里 import 了、但两个清单都没声明」这类缺陷
# （历史 bug：oss2 被 oss_uploader.py import 却未声明，干净安装后真实入库必失败）。
# 这份清单能自动捕获该类型，而 Task 4 原版的两个断言做不到。

# 已知例外。**每一条都必须是「去掉它测试就会红」的 load-bearing 条目** ——
# 该不变式由 test_known_unresolved_entries_are_load_bearing 断言，防止有人为了
# 让红灯变绿而随手往这里塞包名。
#
# 惰性条目（如 duckdb —— 已在两清单声明、解析也稳定）一律不放：
# 它们不影响结果，却会让人误以为豁免清单是个可以随手添加的地方。
_KNOWN_UNRESOLVED: frozenset[str] = frozenset({
    "jieba",          # 软依赖：index_registry.py 在 try/except 内，有 bigram fallback，刻意不声明
    "langchain_core", # 刻意不声明：由 langchain / langgraph 硬性传递保证
})

# 命名空间包根：一个 import 根映射到多个 dist，且**都不在**清单里也不算缺失。
# 危险点：若只声明了家族中的某一个，其余会被静默放过（曾实测 opentelemetry 6/6、
# google 8/8 未被声明却全部通过）。故此类根必须显式登记，新增即意味着一次人工确认。
_NAMESPACE_ROOTS: frozenset[str] = frozenset({
    "langgraph",      # 3 候选：langgraph / langgraph-checkpoint / langgraph-prebuilt
    "opentelemetry",  # 6 候选：opentelemetry-api / -sdk / -proto 等
    "google",         # 8 候选：google-genai / google-api-core / protobuf 等（langextract 传递）
})

# 声明清单里用的是 **dist 名**（python-docx / PyJWT / PyYAML），
# 而代码里 import 的是 **顶层模块名**（docx / jwt / yaml）。
# 必须先经 packages_distributions() 把 import 名映射到 dist 名，再比对。


def _iter_source_files() -> list[Path]:
    """backend 下项目自身的 .py（排除 .venv / tests / scripts / 缓存）。"""
    skip = {".venv", "tests", "scripts", "__pycache__", "output", "node_modules"}
    return [
        p
        for p in _BACKEND.rglob("*.py")
        if not (skip & set(p.relative_to(_BACKEND).parts))
    ]


def _top_level_imports(path: Path) -> set[str]:
    """返回文件中任意位置 import 语句引用的**根模块名**。

    注意是 ast.walk（会进入函数体 / try 块），因此延迟 import 也会被收集；
    「根模块名」指 x.y.z 中的 x，而非「顶层语句」。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def test_code_imports_are_declared():
    """代码里 import 的第三方包，必须出现在 pyproject/requirements 清单中。

    这条是 Task 4 的核心防线：任何「imported but undeclared」的新依赖都会在此失败。
    """
    declared = _pyproject_deps() | _requirements_deps() | {"langextract"}
    distributions = importlib_metadata.packages_distributions()

    missing: dict[str, str] = {}  # dist 名（或多候选根）-> 证据
    for path in _iter_source_files():
        for name in _top_level_imports(path):
            if name in _KNOWN_UNRESOLVED:
                continue
            dists = distributions.get(name)
            if not dists:
                # 未安装、也非已注册的第三方 → 本地模块或 stdlib，不参与比对
                continue

            if len(dists) == 1:
                # 单候选：import 名与 dist 名一一对应，直接比对
                if _normalize(dists[0]) not in declared:
                    missing.setdefault(
                        dists[0], f"{path.relative_to(_BACKEND)} imports {name!r}"
                    )
            else:
                # 多候选（命名空间包）：登记过的根放行（已在 _NAMESPACE_ROOTS 注明理由）；
                # 未登记的根，只有当**没有任何一个**候选 dist 被声明时才报缺失。
                if name in _NAMESPACE_ROOTS:
                    continue
                if not any(_normalize(d) in declared for d in dists):
                    missing.setdefault(
                        name,
                        f"{path.relative_to(_BACKEND)} imports {name!r} (候选: {dists})",
                    )

    assert not missing, (
        "以下包代码已 import、但未在两份清单声明"
        "（或未登记进 _KNOWN_UNRESOLVED / _NAMESPACE_ROOTS）：\n"
        + "\n".join(f"  {k}  ({v})" for k, v in sorted(missing.items()))
    )


def test_known_unresolved_entries_are_load_bearing():
    """_KNOWN_UNRESOLVED 里每一条都必须「去掉它测试就会红」。

    防止把豁免清单当垃圾桶：随手塞一个包名让红灯变绿，会让本测试立刻变红。
    惰性条目（既不被 import、或本来就能通过）应直接删除，而不是留在清单里。
    """
    declared = _pyproject_deps() | _requirements_deps() | {"langextract"}
    distributions = importlib_metadata.packages_distributions()

    imported: set[str] = set()
    for path in _iter_source_files():
        imported |= _top_level_imports(path)

    inert: list[str] = []
    for name in sorted(_KNOWN_UNRESOLVED):
        if name not in imported:
            inert.append(f"{name}（源码未 import，豁免无意义）")
            continue
        dists = distributions.get(name)
        if not dists:
            inert.append(f"{name}（解析为本地/未知模块，不走缺失判定）")
            continue
        if len(dists) == 1:
            passed = _normalize(dists[0]) in declared
        else:
            passed = any(_normalize(d) in declared for d in dists)
        if passed:
            inert.append(f"{name}（已声明，去掉豁免仍会通过）")

    assert not inert, (
        "_KNOWN_UNRESOLVED 存在惰性条目，请删除（豁免清单只装 load-bearing 条目）：\n"
        + "\n".join(f"  {x}" for x in inert)
    )
```

- [ ] **Step 2: 运行测试，确认 2 passed**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_supply_chain.py -v --tb=short`
Expected: 2 passed（`test_requirements_matches_pyproject` + `test_code_imports_are_declared`）

- [ ] **Step 3: 验证新测试非空转（关键）**

临时在某个源文件加一行 `import boto3`（boto3 已安装但未声明），运行测试应 **FAIL** 并指出 boto3；确认后**撤销该临时改动**。

Run: `cd backend && echo "import boto3" >> /tmp/probe.py && cp /tmp/probe.py probe_delete_me.py && .venv/Scripts/python.exe -m pytest tests/test_supply_chain.py::test_code_imports_are_declared -v --tb=short; rm -f probe_delete_me.py`
Expected: FAIL，报出 `boto3`

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_supply_chain.py
git commit -m "test(backend): 用 AST 泛化检查替换两个同义反复断言，覆盖 imported-but-undeclared 缺陷类"
```

---

## Task 5: CI 依赖审计 job

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: 在 `jobs:` 下新增 dependency-audit job**

在 `ci.yml` 的 `jobs:` 块内、`lint:` 之后插入：

```yaml
  dependency-audit:
    runs-on: ubuntu-latest
    env:
      # 锁文件绑定阿里云镜像，CI 必须设同一索引，否则 --check 必然失败
      UV_DEFAULT_INDEX: https://mirrors.aliyun.com/pypi/simple/
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: 校验锁文件与 pyproject 同步
        working-directory: ./backend
        run: uv lock --check

      - name: 依赖漏洞审计（高危阻断）
        working-directory: ./backend
        run: |
          # 不用 `pip install pip-audit`：扫描器自身也必须走锁定来源，
          # 否则一个做供应链检查的 job 却在无版本约束地拉取工具，自相矛盾。
          # pip-audit 已在 pyproject [dependency-groups].dev 声明并被 uv.lock 锁定。
          uv tool run pip-audit -r requirements.txt --strict --desc on
```

- [ ] **Step 2: 本地验证 uv lock --check 可运行**

Run: `cd backend && uv lock --check && echo "LOCK OK"`
Expected: `LOCK OK`（若失败说明 Task 2 的锁文件与 pyproject 不同步，需重跑 `uv lock`）

- [ ] **Step 3: 本地验证 pip-audit 可运行**

Run: `cd backend && pip install pip-audit -q && pip-audit -r requirements.txt --desc on 2>&1 | tail -15`
Expected: 输出漏洞列表或 "No known vulnerabilities found"。记录发现的漏洞供 Task 8 决策。

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: 新增 dependency-audit job（锁文件校验 + pip-audit 漏洞审计）"
```

---

## Task 6: CI 密钥扫描 job + 本地 pre-commit

**Files:**
- Create: `.pre-commit-config.yaml`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: 创建 detect-secrets 基线文件**

Run: `cd /d/graghRAG-agent && pip install detect-secrets -q && detect-secrets scan --exclude-files '\.venv/|node_modules/|uv\.lock|pnpm-lock\.yaml' > .secrets.baseline`
Expected: 生成 `.secrets.baseline` 文件

- [ ] **Step 2: 审计基线，确认无真实密钥被漏报为"允许"**

Run: `cd /d/graghRAG-agent && detect-secrets audit .secrets.baseline --report`
Expected: 输出所有被检出的疑似项。**逐个确认**：若发现真实密钥 → 立即轮换并清理 git 历史；若为误报（如 `settings.local.json` 里的示例）→ 标记为 false positive。

- [ ] **Step 3: 创建 .pre-commit-config.yaml**

```yaml
# 本地提交前防护：密钥扫描 + 大文件拦截
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.5.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
        exclude: |
          (?x)^(
            .*\.venv/.*|
            .*node_modules/.*|
            .*uv\.lock|
            .*pnpm-lock\.yaml|
            .*\.secrets\.baseline
          )$
```

- [ ] **Step 4: 本地验证 pre-commit 可运行**

Run: `cd /d/graghRAG-agent && pip install pre-commit -q && pre-commit run detect-secrets --all-files 2>&1 | tail -10`
Expected: `Passed` 或列出未基线化的疑似项（需补进 baseline 或修正）

- [ ] **Step 5: CI 新增 secret-scan job**

在 `ci.yml` 的 `jobs:` 块内追加：

```yaml
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # 需要完整历史以扫描提交

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: 安装 detect-secrets
        run: pip install detect-secrets

      - name: 密钥扫描
        run: detect-secrets scan --baseline .secrets.baseline
```

- [ ] **Step 6: Commit**

```bash
git add .pre-commit-config.yaml .secrets.baseline .github/workflows/ci.yml
git commit -m "ci: 新增 secret-scan job 与 pre-commit 密钥扫描防护"
```

---

## Task 7: CI 导入冒烟 job

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: 在 `test` job 的 "Install backend dependencies" 步骤后插入冒烟校验**

在 `ci.yml` 的 `test.jobs[].steps` 中，`Install backend dependencies` 之后插入：

```yaml
      - name: 导入冒烟校验（真实入库链路依赖齐全）
        working-directory: ./backend
        run: python scripts/check_imports.py
```

- [ ] **Step 2: 同时把测试安装方式改为锁定安装**

将 `Install backend dependencies` 一步替换为：

```yaml
      - name: Install backend dependencies (locked)
        working-directory: ./backend
        env:
          UV_DEFAULT_INDEX: https://mirrors.aliyun.com/pypi/simple/
        run: |
          pip install uv
          # 运行依赖 + 已锁定的 dev 工具（pytest / pytest-timeout 均在
          # pyproject [dependency-groups].dev 声明并被 uv.lock 锁定），
          # 避免无版本约束的 pip install 造成扫描/测试工具自身漂移。
          uv pip install --system --group dev
          uv pip install --system -r requirements.txt
```

> 说明：CI 已用 `pytest --timeout=60`（`ci.yml:69`）但从未安装 `pytest-timeout` —— 这是一个**既有 CI bug**，本 Task 顺带修复。另：CI 无 langextract 本地路径，但 `scripts/check_imports.py` 不校验 langextract（不在 REQUIRED_MODULES 内），故不会误报。
>
> ⚠️ `uv pip install --group dev` 需要 `pyproject.toml` 存在（Task 1 已建立）。若 uv 版本不支持 `--group`，退回 `uv pip install --system pytest pytest-timeout` 亦可接受——但优先用锁定来源。

- [ ] **Step 3: 本地验证脚本在无 langextract 场景下不误报**

Run: `cd backend && .venv/Scripts/python.exe scripts/check_imports.py`
Expected: 退出码 0（langextract 不在校验列表内，不报错）

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: test job 增加导入冒烟校验，安装改为锁定模式"
```

---

## Task 8: 漏洞处置与记录

> **⚠️ 前置事实（Task 5 实测发现，已独立复现）**：`pip-audit -r requirements.txt` 报 **chromadb 1.5.9 有 5 条漏洞且全部无 Fix Version**：
>
> | CVE | 类型 | 影响面 |
> |-----|------|--------|
> | PYSEC-2026-311 | 预认证代码注入（`trust_remote_code`） | ChromaDB **服务器模式** HTTP 端点 |
> | PYSEC-2026-3814 | 认证后代码注入（需 UPDATE_COLLECTION） | 同上 |
> | PYSEC-2026-3815 | `SimpleRBACAuthorizationProvider` 不校验租户边界 | 同上（鉴权组件） |
> | PYSEC-2026-3813 | 缺失授权校验，可跨租户读写删 | 同上 |
>
> 由于无 fix version，`pip-audit --strict` 会让 CI **必然红灯**。
>
> **可利用性判定（需在 Task 8 复核并落档）**：
> - 本应用 `vector_store.py:64,71` 使用 **`chromadb.PersistentClient`（嵌入式）**，仓库内**零处** `HttpClient`，也没有读 `CHROMADB_HOST`
> - 5 条 CVE 全部作用于 **ChromaDB 服务器模式的 HTTP 端点与鉴权组件**，嵌入式客户端不经过这些路径
> - **但**：`docker-compose.yml:26` 起了 `chromadb/chroma:0.5.23` 服务容器，且 `backend` 设了 `CHROMADB_HOST=chromadb` + `depends_on: service_healthy` —— 即**配置意图是连服务端，代码却没有实现**。这是一处 config/代码不一致（按铁律 7 需修一边）
>
> **Task 8 必须二选一并落档**：
> - **(A) 声明不可利用 + 记录豁免**：确认仅嵌入式使用，把 chromadb 从 compose 服务中移除（或明确标注"预留未启用"），CI 加 `--ignore-vuln` 逐条豁免并写明理由与复查时间
> - **(B) 接受风险**：若确实要暴露 Chroma 服务，则需评估部署网络隔离、把服务容器版本与 PyPI 包版本对齐（服务端是 0.5.23、客户端包是 1.5.9，不同步本身也是隐患）
>
> 推荐 (A)：当前代码路径不支持服务端模式，且有 3 条 CVE 在 `0.4.17` / `0.5.0` 起即受影响，降级 python 包并不能解决。

**Files:**
- Create: `docs/governance/dependency-audit-2026-09-17.md`

- [ ] **Step 1: 跑完整审计并记录结果**

Run: `cd backend && uv pip install --system pip-audit 2>/dev/null; pip-audit -r requirements.txt --desc on > /tmp/audit.txt 2>&1; cat /tmp/audit.txt`
Expected: 输出 CVE 列表（可能为空）

- [ ] **Step 2: 写审计记录文档**

```markdown
# 依赖漏洞审计记录

> 日期：2026-09-17
> 范围：backend/requirements.txt
> 工具：pip-audit

## 审计结果

Found 5 known vulnerabilities in 1 package（4 个唯一 CVE，全部无 Fix Version）

## 处置决策

| 包 | CVE | 处置 | 理由 |
|----|-----|------|------|
| chromadb 1.5.9 | PYSEC-2026-311 | CI --ignore-vuln 豁免 | 预认证代码注入，作用于服务端模式 HTTP 端点 |
| chromadb 1.5.9 | PYSEC-2026-3814 | 同上 | 认证后代码注入，需服务端 UPDATE_COLLECTION 权限 |
| chromadb 1.5.9 | PYSEC-2026-3815 | 同上 | SimpleRBACAuthorizationProvider（服务端鉴权组件） |
| chromadb 1.5.9 | PYSEC-2026-3813 | 同上 | 服务端缺失授权校验，跨租户读写 |

共性：全部作用于 ChromaDB **服务端模式**；本应用用 `chromadb.PersistentClient`
（嵌入式），零 HttpClient、零 CHROMADB_HOST 读取 → 路径不可达。
且 3813 影响 >=0.4.17、3815 影响 >=0.5.0，**降级 python 包无效**。

## 未处置项说明

- **compose 与代码不一致**：docker-compose.yml 起了 chromadb 服务容器并设
  CHROMADB_HOST，但代码从不连接 → 需修一边（推荐移除该服务）。独立任务。
- **版本线不一致**：服务镜像 0.5.23 vs PyPI 包 1.5.9 → 仅在启用服务端模式时才需处理。
- **复查触发条件**：代码引入 HttpClient / 开始读 CHROMADB_HOST / chromadb 出修复版本，
  任一发生即须重新评估并移除豁免。
```

- [ ] **Step 3: Commit**

```bash
git add docs/governance/dependency-audit-2026-09-17.md
git commit -m "docs(governance): 新增依赖漏洞审计记录"
```

---

## Task 9: 更新 LRA 进度

**Files:**
- Modify: `.lra/feature-list.json`
- Modify: `.lra/progress.txt`
- Modify: `backend/CLAUDE.md`

- [ ] **Step 1: 在 backend/CLAUDE.md 补镜像约束说明（弥补质量审查 I1 文档缺口）**

在 `backend/CLAUDE.md` 的安装/环境说明处，追加一段：

```markdown
## 依赖安装（uv 锁文件）

本项目使用 `uv.lock` 锁定依赖（含哈希），锁文件绑定阿里云镜像。

- 日常开发：`uv sync --locked`（本机可直连阿里云，无需额外配置）
- 若要重新解析依赖：`uv lock --default-index https://mirrors.aliyun.com/pypi/simple/`
  （不带该参数会尝试直连 pypi.org，本机网络下会超时）
- CI：`.github/workflows/ci.yml` 中已设 `UV_DEFAULT_INDEX`，勿删
- ⚠️ 锁文件把下载 URL 也写死为阿里云。若在无法访问 `mirrors.aliyun.com`
  的环境构建，需重新生成锁文件，仅改环境变量无效。

旧的 `uv pip install -r requirements.txt` 仍然可用（不读锁文件）。
```

- [ ] **Step 2: 标记 F001 / F002 完成**

将 `.lra/feature-list.json` 中 F001、F002 的 `status` 改为 `"completed"`，填入 `completed_at` 与 `session` 编号。

- [ ] **Step 3: 追加 session 记录到 progress.txt**

在 `.lra/progress.txt` 末尾追加本次 session 的 checkpoint 记录（参照文件内既有格式）。

- [ ] **Step 4: Commit**

```bash
git add .lra/feature-list.json .lra/progress.txt backend/CLAUDE.md
git commit -m "chore(lra): 标记 F001/F002 供应链治理完成，补 uv 镜像约束说明"
```

---

## 验收标准

全部完成后，以下须成立：

1. `cd backend && uv lock --check` 退出码 0
2. `cd backend && uv sync --locked` 可在干净环境复现安装
3. `cd backend && python scripts/check_imports.py` 退出码 0，含 `oss2`
4. `cd backend && pytest tests/test_supply_chain.py` 3 passed
5. `git ls-files backend/uv.lock` 有输出（锁文件已提交）
6. CI 出现 `dependency-audit` / `secret-scan` 两个新 job 且为 required
7. `pip-audit` 高危项为 0，或有处置记录

---

## 已知风险

| 风险 | 应对 |
|------|------|
| `uv lock` 因 langextract 本地路径解析失败 | 确认 `langextract/pyproject.toml` 的 `[project].name == "langextract"`；必要时改用 `tool.uv.sources` 的 `path` 绝对写法 |
| CI 装 uv 后 `uv pip install --system` 与既有 Dockerfile 冲突 | 不动 Dockerfile；本计划只改 CI 的 test job 安装步骤 |
| detect-secrets 基线误报爆炸 | 第 6 步 Task 先 `--report` 审计再提交基线；排除 `settings.local.json` 等已知样例文件 |
| `sentence-transformers` 拉取 torch 导致 CI 变慢 | 已在 CI 服务中限制；若超时，可将该模块移出 REQUIRED_MODULES 并单独标记 |
