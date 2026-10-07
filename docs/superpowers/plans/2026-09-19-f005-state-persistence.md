# F005 状态持久化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将任务、文档和知识图谱版本元数据从进程内全局状态迁移到 SQLite，并通过启动迁移、租户作用域、stale 任务恢复和 KG 原子发布保证重启与多进程一致性。

**Architecture:** SQLite 是任务/文档/KG 版本元数据的唯一运行时真相源；节点和边 payload 继续保存在 JSON artifact 中。所有数据库访问通过 `AccessContext` 作用域化，KG artifact 先写入 staging 目录并生成 manifest，再原子发布为不可变版本目录，最后由 SQLite 激活版本。旧 JSON 只作为启动迁移和兼容读取来源，不与 SQLite 双写。

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, stdlib `sqlite3`, NetworkX, pytest, structlog。

---

## 0. 已冻结的范围与实施规则

这不是把三个全局变量简单替换成数据库；它包含相互依赖的数据库 schema、迁移、任务/文档 Store、KG artifact 发布和路由切换。因此本计划将 F005 拆成连续的可测试子项目，但所有子项目共用同一份 SQLite schema 与作用域契约，不能并行修改同一文件。

已确认的约束：

- SQLite 保存 `tasks`、`documents`、`kg_versions`、`tombstones` 元数据；节点/边仍是 JSON。
- 启动时迁移 `output/tasks_store.json`、`output/docs_store.json` 和既有 `output/kg/**`；原文件先备份、迁移幂等。
- 服务重启时把 `pending/running` 等非终态任务标为内部 `stale`，公开 `TaskStatus` 仍只使用 `pending/running/done/failed`；不自动重跑。
- 每个 Store 读写都需要显式 `AccessContext`；`owner_id`、`tenant_id`、`org_id`、`project_id` 不允许为空。
- 删除先写 tombstone、撤销 active KG，再按数据库登记的精确路径清理文件；未知或越权文档返回 404。
- `kg_builder.py` 的实体关系匹配问题不属于本计划；不要在 F005 中修改关系推断算法。
- 不迁移 ChromaDB、BM25/Table runtime index、conversation、feedback、lineage 或 tenant project JSON。

现有基线必须保留在执行记录中：`cd backend && .venv/Scripts/python.exe -m pytest -q` 当前为 `425 passed, 5 failed`，5 个失败是 `tests/test_phase2.py` 依赖真实 `output/kg` fixture 的数据失败，不得将其误报为 F005 回归。

---

## 1. 文件地图

### 新建文件

- `backend/persistence/__init__.py`：只导出公开 Store、context 和初始化函数；不得在此执行数据库初始化。
- `backend/persistence/context.py`：定义 `AccessContext`、`SystemContext` 和从 `request.state.tenant` 构造普通作用域的函数。
- `backend/persistence/schema.py`：保存有序 migration SQL、schema checksum 和 `initialize_database()`。
- `backend/persistence/sqlite.py`：创建短生命周期 SQLite 连接，开启 WAL、外键和 busy timeout，提供事务上下文。
- `backend/persistence/task_store.py`：任务创建、进度、失败、完成、按作用域读取和启动 stale 标记。
- `backend/persistence/document_store.py`：文档 upsert/list/get/delete-state 和 tombstone 写入。
- `backend/persistence/kg_metadata_store.py`：KG 版本元数据、版本分配、active/obsolete 状态和 reconcile 查询。
- `backend/persistence/artifact_store.py`：staging JSON、manifest/hash 校验、同文件系统原子发布和 artifact 读取。
- `backend/persistence/migration.py`：旧 JSON/旧 KG 布局备份、导入和重复运行保护。
- `backend/persistence/service.py`：将 artifact、KG 元数据、文档和任务完成操作编排为明确的 SQLite 事务。

### 修改文件

- `backend/server.py:189-235`：lifespan 中先初始化/迁移/恢复业务状态，再加载运行时 KG。
- `backend/routes/ingest.py:23-153,155-294`：移除 `_tasks` 作为真相源，改调 `TaskStore`/`IngestService`。
- `backend/routes/__init__.py:27-67`：将文档 facade 改为 Store 适配层，不再维护 `_docs_store` 列表。
- `backend/routes/documents.py:19-126`：所有读写接收 `Request` 作用域；删除使用 tombstone 和精确资产路径。
- `backend/routes/graph.py:32-168`：只从当前作用域的 active 文档/版本读取图谱。
- `backend/routes/health.py:72-166`：文档和 KG 统计从 Store 读取。
- `backend/routes/query.py:46-100`：`load_all_kg_graphs`/`reload_kg` 使用 active artifact 快照。
- `backend/kg_store.py:293-525`：保留旧读取 API，但优先使用 SQLite active 元数据；旧 JSON 仅兼容读取。
- `backend/worker.py:1081-1090`：禁止直接覆写 `nodes.json`/`edges.json`，改调用 artifact 发布服务。
- `backend/models.py:141-162`：保持现有 response 字段；只在确有需要时增加向后兼容的可选字段，不新增公开 stale 状态。
- `backend/services/backup.py:24-130`：将 SQLite、manifest、旧 JSON 迁移备份纳入备份清单。
- `backend/CLAUDE.md`：更新业务状态的真实存储和 JSON 兼容期说明。

### 新建测试文件

- `backend/tests/test_persistence_context.py`
- `backend/tests/test_persistence_sqlite.py`
- `backend/tests/test_persistence_task_store.py`
- `backend/tests/test_persistence_document_store.py`
- `backend/tests/test_persistence_migration.py`
- `backend/tests/test_persistence_artifact_store.py`
- `backend/tests/test_persistence_api.py`

测试全部使用 `tmp_path` 的真实 SQLite 和真实文件系统；不得用 mock Store 验证 SQLite 行为。

---

## Task 1: 冻结作用域和 API 契约

**Files:**
- Create: `backend/persistence/__init__.py`
- Create: `backend/persistence/context.py`
- Create: `backend/tests/test_persistence_context.py`
- Modify: `backend/middleware/tenant_middleware.py:101-107` only if normalization is needed
- Modify: `backend/models.py:18-23,141-162` only if contract assertions require no code change

### Step 1: Write the failing tests

Create `backend/tests/test_persistence_context.py` with:

```python
from types import SimpleNamespace

import pytest

from persistence.context import AccessContext, SystemContext, context_from_request


def test_context_from_request_normalizes_missing_project_id():
    request = SimpleNamespace(
        state=SimpleNamespace(
            tenant={
                "org_id": "org-a",
                "project_id": None,
                "user_id": "user-a",
                "org_role": "org_editor",
            }
        )
    )

    context = context_from_request(request)

    assert context == AccessContext(
        owner_id="user-a",
        tenant_id="org-a/default",
        org_id="org-a",
        project_id="default",
    )


def test_context_rejects_missing_owner_and_tenant():
    request = SimpleNamespace(
        state=SimpleNamespace(
            tenant={"org_id": "", "project_id": "p1", "user_id": ""}
        )
    )

    with pytest.raises(ValueError, match="owner_id"):
        context_from_request(request)


def test_system_context_is_explicit_and_cannot_be_used_as_access_context():
    system = SystemContext(reason="startup reconciliation")

    assert system.reason == "startup reconciliation"
    assert not isinstance(system, AccessContext)
```

Add a contract test to the same file:

```python

def test_task_status_wire_contract_has_no_internal_stale_value():
    from models import TaskStatus

    assert {item.value for item in TaskStatus} == {"pending", "running", "done", "failed"}
```

### Step 2: Run the tests and verify they fail

Run:

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_context.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'persistence.context'`.

### Step 3: Implement the context types

Create `backend/persistence/context.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AccessContext:
    owner_id: str
    tenant_id: str
    org_id: str
    project_id: str

    def __post_init__(self) -> None:
        for name in ("owner_id", "tenant_id", "org_id", "project_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True, slots=True)
class SystemContext:
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("system context reason must not be empty")


def context_from_request(request: Any) -> AccessContext:
    tenant = getattr(getattr(request, "state", None), "tenant", None) or {}
    org_id = str(tenant.get("org_id") or "default")
    project_id = str(tenant.get("project_id") or "default")
    owner_id = str(tenant.get("user_id") or "")
    return AccessContext(
        owner_id=owner_id,
        tenant_id=f"{org_id}/{project_id}",
        org_id=org_id,
        project_id=project_id,
    )


def legacy_context() -> AccessContext:
    return AccessContext(
        owner_id="legacy",
        tenant_id="default/default",
        org_id="default",
        project_id="default",
    )
```

Create `backend/persistence/__init__.py`:

```python
from persistence.context import AccessContext, SystemContext, context_from_request, legacy_context

__all__ = ["AccessContext", "SystemContext", "context_from_request", "legacy_context"]
```

Do not modify `TaskStatus`; the test must pass against the existing enum.

### Step 4: Run the tests and verify they pass

Run:

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_context.py
```

Expected: `4 passed`.

### Step 5: Commit the isolated contract

```bash
git add backend/persistence/__init__.py backend/persistence/context.py backend/tests/test_persistence_context.py
 git commit -m "feat(storage): define persistence access context"
```

---

## Task 2: Add SQLite connection and schema migrations

**Files:**
- Create: `backend/persistence/sqlite.py`
- Create: `backend/persistence/schema.py`
- Create: `backend/tests/test_persistence_sqlite.py`
- Modify: `backend/persistence/__init__.py`

### Step 1: Write failing database tests

Create `backend/tests/test_persistence_sqlite.py`:

```python
import sqlite3

import pytest

from persistence.schema import initialize_database
from persistence.sqlite import transaction


def test_initialize_database_creates_business_tables_and_pragmas(tmp_path):
    db_path = tmp_path / "state.sqlite3"

    initialize_database(db_path)
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"schema_migrations", "tasks", "documents", "kg_versions", "tombstones"} <= tables
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_initialize_database_is_idempotent(tmp_path):
    db_path = tmp_path / "state.sqlite3"

    initialize_database(db_path)
    initialize_database(db_path)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1


def test_transaction_rolls_back_on_exception(tmp_path):
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)

    with pytest.raises(RuntimeError, match="rollback sentinel"):
        with transaction(db_path) as conn:
            conn.execute(
                "INSERT INTO tasks(task_id, owner_id, tenant_id, org_id, project_id, status, filename, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("t1", "u1", "o1/p1", "o1", "p1", "pending", "a.pdf", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
            )
            raise RuntimeError("rollback sentinel")

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0


def test_only_one_active_kg_version_is_allowed(tmp_path):
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)

    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO documents(document_id, owner_id, tenant_id, org_id, project_id, filename, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("doc-1", "u1", "o1/p1", "o1", "p1", "a.pdf", "indexed", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        conn.execute(
            "INSERT INTO kg_versions(tenant_id, document_id, version, owner_id, org_id, project_id, state, artifact_relpath, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("o1/p1", "doc-1", 1, "u1", "o1", "p1", "active", "kg/doc-1/v1", "2026-01-01T00:00:00+00:00"),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO kg_versions(tenant_id, document_id, version, owner_id, org_id, project_id, state, artifact_relpath, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("o1/p1", "doc-1", 2, "u1", "o1", "p1", "active", "kg/doc-1/v2", "2026-01-01T00:00:00+00:00"),
            )
```

### Step 2: Run the tests and verify they fail

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_sqlite.py
```

Expected: FAIL because `persistence.schema` and `persistence.sqlite` do not exist.

### Step 3: Implement the schema and transaction helper

`backend/persistence/sqlite.py` must provide these exact functions:

```python
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except BaseException:
            conn.rollback()
            raise
        else:
            conn.commit()
```

`backend/persistence/schema.py` must define the schema in one migration string and record a SHA-256 checksum:

```python
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from persistence.sqlite import transaction

SCHEMA_VERSION = 1
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','running','done','failed')),
    lifecycle_status TEXT NOT NULL DEFAULT 'active' CHECK (lifecycle_status IN ('active','stale','deleted')),
    stage TEXT,
    filename TEXT NOT NULL,
    file_size_bytes INTEGER NOT NULL DEFAULT 0,
    source_filepath TEXT,
    progress_json TEXT,
    result_json TEXT,
    error_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    row_version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    status TEXT NOT NULL,
    kg_nodes INTEGER,
    kg_edges INTEGER,
    pages INTEGER,
    indexed_at TEXT,
    file_size_bytes INTEGER,
    filepath TEXT,
    active_kg_version INTEGER,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, document_id)
);
CREATE TABLE IF NOT EXISTS kg_versions (
    tenant_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    owner_id TEXT NOT NULL,
    org_id TEXT NOT NULL,
    project_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('staged','ready','active','obsolete','deleted')),
    artifact_relpath TEXT NOT NULL,
    manifest_sha256 TEXT,
    node_count INTEGER NOT NULL DEFAULT 0,
    edge_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    activated_at TEXT,
    PRIMARY KEY (tenant_id, document_id, version),
    FOREIGN KEY (tenant_id, document_id) REFERENCES documents(tenant_id, document_id)
);
CREATE TABLE IF NOT EXISTS tombstones (
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    deleted_at TEXT NOT NULL,
    reason TEXT,
    PRIMARY KEY (resource_type, tenant_id, resource_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_kg_per_document
    ON kg_versions(tenant_id, document_id) WHERE state = 'active';
CREATE INDEX IF NOT EXISTS tasks_scope_idx ON tasks(tenant_id, owner_id, updated_at);
CREATE INDEX IF NOT EXISTS documents_scope_idx ON documents(tenant_id, owner_id, status);
"""


def initialize_database(db_path: str | Path) -> None:
    checksum = hashlib.sha256(SCHEMA_SQL.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    with transaction(db_path) as conn:
        row = conn.execute(
            "SELECT checksum FROM schema_migrations WHERE version = ?",
            (SCHEMA_VERSION,),
        ).fetchone()
        if row and row[0] != checksum:
            raise RuntimeError("schema checksum mismatch for version 1")
        if row:
            return
        conn.executescript(SCHEMA_SQL)
        conn.execute(
            "INSERT INTO schema_migrations(version, checksum, applied_at) VALUES (?, ?, ?)",
            (SCHEMA_VERSION, checksum, now),
        )
```

### Step 4: Run the tests and verify they pass

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_sqlite.py
```

Expected: `4 passed`.

### Step 5: Commit

```bash
git add backend/persistence/sqlite.py backend/persistence/schema.py backend/tests/test_persistence_sqlite.py
 git commit -m "feat(storage): add sqlite schema and transactions"
```

---

## Task 3: Implement the task Store and stale recovery

**Files:**
- Create: `backend/persistence/task_store.py`
- Create: `backend/tests/test_persistence_task_store.py`
- Modify: `backend/persistence/__init__.py`

### Step 1: Write failing Store tests

```python
from datetime import datetime, timezone

import pytest

from persistence.context import AccessContext
from persistence.schema import initialize_database
from persistence.task_store import TaskStore


@pytest.fixture
def context():
    return AccessContext("user-a", "org-a/project-a", "org-a", "project-a")


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)
    return TaskStore(db_path)


def test_create_and_get_task_round_trips_datetime_and_json(store, context):
    created = datetime(2026, 9, 19, tzinfo=timezone.utc)
    store.create(
        context,
        task_id="task-1",
        filename="a.pdf",
        file_size_bytes=42,
        source_filepath="uploads/task-1_a.pdf",
        created_at=created,
    )

    task = store.get(context, "task-1")

    assert task["task_id"] == "task-1"
    assert task["status"] == "pending"
    assert task["created_at"] == created
    assert task["updated_at"] == created


def test_get_does_not_cross_tenant_scope(store, context):
    other = AccessContext("user-b", "org-b/project-b", "org-b", "project-b")
    store.create(context, task_id="task-a", filename="a.pdf", file_size_bytes=1)

    assert store.get(other, "task-a") is None


def test_mark_stale_changes_wire_status_to_failed_and_keeps_internal_marker(store, context):
    store.create(context, task_id="task-1", filename="a.pdf", file_size_bytes=1)
    store.set_status(context, "task-1", "running", stage="extraction")

    changed = store.mark_inflight_stale()
    task = store.get(context, "task-1")

    assert changed == 1
    assert task["status"] == "failed"
    assert task["lifecycle_status"] == "stale"
    assert task["error"]["code"] == "TASK_STALE_AFTER_RESTART"


def test_compare_and_set_rejects_old_row_version(store, context):
    store.create(context, task_id="task-1", filename="a.pdf", file_size_bytes=1)

    assert store.set_status(context, "task-1", "running", stage="mineru", expected_row_version=0)
    assert not store.set_status(context, "task-1", "done", stage="completed", expected_row_version=0)
```

### Step 2: Run the tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_task_store.py
```

Expected: FAIL because `TaskStore` is undefined.

### Step 3: Implement the Store API

The implementation must expose these methods with these signatures:

```python
class TaskStore:
    def __init__(self, db_path: str | Path): ...
    def create(self, context: AccessContext, *, task_id: str, filename: str,
               file_size_bytes: int, source_filepath: str | None = None,
               created_at: datetime | None = None) -> None: ...
    def get(self, context: AccessContext, task_id: str) -> dict | None: ...
    def set_status(self, context: AccessContext, task_id: str, status: str, *,
                   stage: str | None, expected_row_version: int | None = None) -> bool: ...
    def update_progress(self, context: AccessContext, task_id: str, *, stage: str,
                        progress: dict, result: dict | None = None,
                        expected_row_version: int | None = None) -> bool: ...
    def complete(self, context: AccessContext, task_id: str, *, stage: str,
                 result: dict, expected_row_version: int | None = None) -> bool: ...
    def fail(self, context: AccessContext, task_id: str, *, stage: str,
             error: dict, expected_row_version: int | None = None) -> bool: ...
    def mark_inflight_stale(self) -> int: ...
```

Implementation requirements:

- Serialize `progress`, `result`, and `error` with `json.dumps(..., ensure_ascii=False)`.
- Serialize datetimes with `datetime.isoformat()` and parse with `datetime.fromisoformat()` on read.
- Every query includes `owner_id=? AND tenant_id=?`; `mark_inflight_stale()` is the sole startup/system operation without request scope.
- `set_status`, `update_progress`, `complete`, and `fail` update `row_version=row_version+1` and add `expected_row_version` to the `WHERE` clause when supplied.
- `mark_inflight_stale()` executes one transaction over `status IN ('pending','running')`, sets `status='failed'`, `lifecycle_status='stale'`, and JSON error code `TASK_STALE_AFTER_RESTART`.

Concrete update pattern:

```python
where = "task_id = ? AND owner_id = ? AND tenant_id = ?"
params = [task_id, context.owner_id, context.tenant_id]
if expected_row_version is not None:
    where += " AND row_version = ?"
    params.append(expected_row_version)
result = conn.execute(
    f"UPDATE tasks SET status=?, stage=?, updated_at=?, row_version=row_version+1 WHERE {where}",
    [status, stage, now, *params],
)
return result.rowcount == 1
```

### Step 4: Run focused and regression tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_task_store.py tests/test_ingest_degraded_status.py
```

Expected: new Store tests pass; existing degraded-status tests remain unchanged and pass.

### Step 5: Commit

```bash
git add backend/persistence/task_store.py backend/tests/test_persistence_task_store.py backend/persistence/__init__.py
 git commit -m "feat(storage): persist task lifecycle in sqlite"
```

---

## Task 4: Implement document Store and tombstones

**Files:**
- Create: `backend/persistence/document_store.py`
- Create: `backend/tests/test_persistence_document_store.py`
- Modify: `backend/routes/__init__.py:27-67`
- Modify: `backend/routes/documents.py:19-101`

### Step 1: Write failing Store and deletion tests

```python
from persistence.context import AccessContext
from persistence.document_store import DocumentStore
from persistence.schema import initialize_database


def test_document_store_filters_by_tenant_and_owner(tmp_path):
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)
    store = DocumentStore(db_path)
    owner_a = AccessContext("user-a", "org-a/project-a", "org-a", "project-a")
    owner_b = AccessContext("user-b", "org-b/project-b", "org-b", "project-b")

    store.upsert(owner_a, {"document_id": "doc-1", "filename": "a.pdf", "status": "indexed"})

    assert len(store.list(owner_a)) == 1
    assert store.list(owner_b) == []
    assert store.get(owner_b, "doc-1") is None


def test_delete_writes_tombstone_and_hides_document(tmp_path):
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)
    store = DocumentStore(db_path)
    context = AccessContext("user-a", "org-a/project-a", "org-a", "project-a")
    store.upsert(context, {"document_id": "doc-1", "filename": "a.pdf", "status": "indexed"})

    assert store.tombstone(context, "doc-1", reason="user request") is True
    assert store.get(context, "doc-1") is None
    assert store.is_tombstoned(context, "doc-1") is True


def test_delete_unknown_document_returns_false(tmp_path):
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)
    store = DocumentStore(db_path)
    context = AccessContext("user-a", "org-a/project-a", "org-a", "project-a")

    assert store.tombstone(context, "missing", reason="user request") is False
```

### Step 2: Run tests and verify failure

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_document_store.py
```

Expected: FAIL because `DocumentStore` is not defined.

### Step 3: Implement Store methods

Use this public API:

```python
class DocumentStore:
    def __init__(self, db_path: str | Path): ...
    def upsert(self, context: AccessContext, document: dict) -> None: ...
    def get(self, context: AccessContext, document_id: str) -> dict | None: ...
    def list(self, context: AccessContext) -> list[dict]: ...
    def tombstone(self, context: AccessContext, document_id: str, *, reason: str) -> bool: ...
    def is_tombstoned(self, context: AccessContext, document_id: str) -> bool: ...
```

Implementation details:

- `upsert` writes all required scope columns and uses `ON CONFLICT(tenant_id, document_id) DO UPDATE`.
- `get` and `list` include `status != 'deleted'` and use both owner and tenant predicates.
- `tombstone` first checks the scoped document, then in one transaction inserts into `tombstones` and updates the document to `status='deleted'`, `active_kg_version=NULL`.
- `tombstone` must not construct a filesystem path from user input.

### Step 4: Replace the document module facade

Replace `_docs_store`, `_load_docs`, `_save_docs`, and the thread-only list mutation in `backend/routes/__init__.py` with a configured `DocumentStore` facade. Keep `get_docs_snapshot(context)` and `add_doc(context, doc)` signatures explicit. Do not add a no-context production fallback; tests that need legacy data must construct `legacy_context()`.

Update `backend/routes/documents.py`:

```python
@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(request: Request):
    context = context_from_request(request)
    docs = get_docs_snapshot(context)
    ...

@router.delete("/documents/{doc_id}", response_model=DeleteResponse)
async def delete_document(doc_id: str, request: Request):
    context = context_from_request(request)
    document = document_store.get(context, doc_id)
    if document is None:
        raise HTTPException(404, detail="Document not found")
    document_store.tombstone(context, doc_id, reason="api delete")
    # Clean only document["filepath"] and the registered KG artifact paths.
    ...
```

The existing prefix loop over `doc_id` and upload filenames must be removed. File deletion may be best-effort after the tombstone, but failures must be logged and must not turn a committed tombstone back into an active document.

### Step 5: Run focused tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_document_store.py tests/test_phase4.py::TestTenantKG
```

Expected: new Store tests pass; existing tenant KG path tests remain passing.

### Step 6: Commit

```bash
git add backend/persistence/document_store.py backend/tests/test_persistence_document_store.py backend/routes/__init__.py backend/routes/documents.py
 git commit -m "feat(storage): scope documents and add tombstones"
```

---

## Task 5: Add idempotent startup migration and stale recovery

**Files:**
- Create: `backend/persistence/migration.py`
- Create: `backend/tests/test_persistence_migration.py`
- Modify: `backend/server.py:189-235`
- Modify: `backend/persistence/schema.py` to add migration audit table if needed

### Step 1: Write migration tests first

```python
import json
import sqlite3

from persistence.migration import migrate_legacy_state
from persistence.schema import initialize_database
from persistence.task_store import TaskStore
from persistence.context import legacy_context


def test_migration_imports_legacy_tasks_and_parses_timestamps(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    tasks_path = output / "tasks_store.json"
    tasks_path.write_text(json.dumps({
        "task-old": {
            "task_id": "task-old",
            "status": "done",
            "stage": "completed",
            "filename": "old.pdf",
            "file_size_bytes": 10,
            "created_at": "2026-09-18T00:00:00+00:00",
            "updated_at": "2026-09-18T00:01:00+00:00",
            "result": {"document_id": "doc-old"},
        }
    }), encoding="utf-8")
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)

    migrate_legacy_state(db_path=db_path, output_dir=output)
    task = TaskStore(db_path).get(legacy_context(), "task-old")

    assert task["status"] == "done"
    assert task["created_at"].isoformat() == "2026-09-18T00:00:00+00:00"
    assert task["result"] == {"document_id": "doc-old"}
    assert (output / "migrations").exists()


def test_migration_is_idempotent(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "tasks_store.json").write_text(json.dumps({
        "task-1": {"task_id": "task-1", "status": "done", "filename": "a.pdf",
                    "file_size_bytes": 1, "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00"}
    }), encoding="utf-8")
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)

    migrate_legacy_state(db_path=db_path, output_dir=output)
    migrate_legacy_state(db_path=db_path, output_dir=output)

    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 1


def test_migration_marks_inflight_tasks_stale(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    (output / "tasks_store.json").write_text(json.dumps({
        "task-1": {"task_id": "task-1", "status": "running", "filename": "a.pdf",
                    "file_size_bytes": 1, "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00"}
    }), encoding="utf-8")
    db_path = tmp_path / "state.sqlite3"
    initialize_database(db_path)

    migrate_legacy_state(db_path=db_path, output_dir=output)

    task = TaskStore(db_path).get(legacy_context(), "task-1")
    assert task["status"] == "failed"
    assert task["lifecycle_status"] == "stale"
    assert task["error"]["code"] == "TASK_STALE_AFTER_RESTART"
```

Add a corruption test asserting the original invalid JSON remains byte-for-byte unchanged and migration raises a typed `LegacyMigrationError` rather than treating it as `{}`.

### Step 2: Run the tests and verify failure

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_migration.py
```

Expected: FAIL because `migrate_legacy_state` does not exist.

### Step 3: Implement the migration API

Expose:

```python
class LegacyMigrationError(RuntimeError):
    pass


def migrate_legacy_state(*, db_path: str | Path, output_dir: str | Path) -> dict:
    """Backup and idempotently import legacy state, then mark inflight tasks stale."""
```

Implementation requirements:

1. Compute SHA-256 for each source file before parsing.
2. Copy sources into `output/migrations/backups/<run_id>/` without deleting the source.
3. Parse invalid JSON with `json.loads`; on failure raise `LegacyMigrationError` after recording the source path and checksum.
4. Insert legacy records with `owner_id='legacy'`, `tenant_id='default/default'`, `org_id='default'`, and `project_id='default'`.
5. Use `INSERT ... ON CONFLICT DO NOTHING` keyed by stable task/document/version IDs.
6. Record source checksum in a `migration_sources(source_path PRIMARY KEY, sha256, imported_at)` table so a second startup does not duplicate rows.
7. Import old KG layouts in this order: `doc_<id>/vN/versions.json`, `doc_<id>/nodes.json + edges.json`, then global `output/kg/nodes.json + edges.json`; create version 1 metadata for flat layouts.
8. Call `TaskStore.mark_inflight_stale()` only after task import has committed.

### Step 4: Integrate startup order

At the beginning of `backend/server.py:190 lifespan`, before `restore_runtime_indexes()` and before `load_all_kg_graphs()`, call:

```python
from persistence.migration import migrate_legacy_state
from persistence.schema import initialize_database

state_db = Path(os.getenv("STATE_DB_PATH", "output/state.sqlite3"))
initialize_database(state_db)
migrate_legacy_state(db_path=state_db, output_dir=Path("output"))
```

If migration fails, log the typed error and refuse write-capable startup; do not continue with an empty in-memory store. The chosen behavior must return an explicit readiness failure rather than silently serving partial state.

### Step 5: Run focused startup tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_migration.py tests/test_runtime_recovery.py
```

Expected: migration tests pass and existing runtime recovery tests remain passing after adding their required `STATE_DB_PATH` temporary fixture.

### Step 6: Commit

```bash
git add backend/persistence/migration.py backend/tests/test_persistence_migration.py backend/server.py backend/persistence/schema.py
 git commit -m "feat(storage): migrate legacy state on startup"
```

---

## Task 6: Replace ingest/status writes with the task Store

**Files:**
- Create: `backend/persistence/service.py`
- Create: `backend/tests/test_persistence_api.py`
- Modify: `backend/routes/ingest.py:23-153,155-294`
- Modify: `backend/routes/__init__.py` only for the document service injection

### Step 1: Write API-level failing tests

Use a real FastAPI `TestClient`, a temporary `STATE_DB_PATH`, and a fake `run_real_pipeline` only for the external pipeline boundary. The database and routes must remain real.

```python

def test_ingest_status_survives_module_reload(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DB_PATH", str(tmp_path / "state.sqlite3"))
    client = build_test_client(monkeypatch)

    response = client.post(
        "/api/v1/ingest",
        files={"file": ("a.docx", b"minimal docx bytes", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    import importlib
    import routes.ingest as ingest_route
    importlib.reload(ingest_route)

    status = client.get(f"/api/v1/status/{task_id}")
    assert status.status_code == 200
    assert status.json()["task_id"] == task_id
    assert isinstance(status.json()["duration_seconds"], int)
```

Add tests for:

```python

def test_pipeline_failure_is_persisted_with_error_code(...): ...
def test_degraded_result_keeps_done_status_and_partial_warning(...): ...
def test_status_from_wrong_tenant_is_404(...): ...
```

The bodies must assert exact existing wire fields: `status`, `stage`, `result.partial`, `result.warnings`, `error.code`, `created_at`, `updated_at`, and `duration_seconds`.

### Step 2: Run tests and verify failure

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_api.py
```

Expected: FAIL because the route still reads process-local `_tasks`, and reloading the module loses the in-memory status.

### Step 3: Implement `IngestService`

`backend/persistence/service.py` must expose:

```python
class IngestService:
    def __init__(self, task_store: TaskStore, document_store: DocumentStore): ...
    def create_task(self, context: AccessContext, *, task_id: str, filename: str,
                    file_size_bytes: int, source_filepath: str | None = None) -> None: ...
    def mark_running(self, context: AccessContext, task_id: str) -> bool: ...
    def update_progress(self, context: AccessContext, task_id: str, *, stage: str,
                        progress: dict, result: dict | None = None) -> bool: ...
    def fail(self, context: AccessContext, task_id: str, *, stage: str, error: dict) -> bool: ...
    def complete(self, context: AccessContext, task_id: str, *, result: dict,
                 document: dict) -> bool: ...
```

`complete` must update the document and task in one SQLite transaction after the KG publish service has returned a validated artifact/version. Keep `partial` and `warnings` inside `result_json`; do not add `degraded` to `TaskStatus`.

Update `routes/ingest.py` as follows:

- Delete `_load_tasks`, `_save_tasks`, and `_tasks` as production state.
- Add `request: Request` to `get_status` and `ingest`.
- Build `context = context_from_request(request)` at the boundary.
- Pass `context` into every task Store call and every progress callback closure.
- Convert the Store dictionary into the unchanged `StatusResponse` Pydantic model.
- Use `HTTPException(404, detail=...)` when a task is absent from the scoped Store.

### Step 4: Run focused and existing tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_api.py tests/test_ingest_degraded_status.py tests/test_errors.py
```

Expected: new API tests and F004 tests pass. Any old test that directly mutates `_tasks` must be rewritten to seed the temporary SQLite Store instead of restoring `_tasks` as a second source of truth.

### Step 5: Commit

```bash
git add backend/persistence/service.py backend/tests/test_persistence_api.py backend/routes/ingest.py backend/routes/__init__.py
 git commit -m "feat(storage): route ingest status through sqlite"
```

---

## Task 7: Add atomic KG artifact publishing and active-version metadata

**Files:**
- Create: `backend/persistence/artifact_store.py`
- Create: `backend/persistence/kg_metadata_store.py`
- Create: `backend/tests/test_persistence_artifact_store.py`
- Modify: `backend/worker.py:1081-1090`
- Modify: `backend/kg_store.py:293-525`
- Modify: `backend/routes/query.py:46-100`

### Step 1: Write failing artifact tests

```python
import json

import pytest

from persistence.artifact_store import ArtifactStore, ArtifactValidationError


def test_publish_creates_manifest_and_atomic_version_directory(tmp_path):
    store = ArtifactStore(tmp_path / "kg")
    result = store.publish(
        tenant_id="org-a/project-a",
        document_id="doc-1",
        version=1,
        nodes=[{"node_id": "n1", "label": "A"}],
        edges=[],
    )

    assert result.relative_path == "org-a/project-a/doc-1/v1"
    version_dir = tmp_path / "kg" / result.relative_path
    assert (version_dir / "nodes.json").exists()
    assert (version_dir / "edges.json").exists()
    manifest = json.loads((version_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["node_count"] == 1
    assert manifest["edge_count"] == 0
    assert not list((tmp_path / "kg" / ".staging").rglob("*"))


def test_publish_rejects_edge_referencing_missing_node(tmp_path):
    store = ArtifactStore(tmp_path / "kg")

    with pytest.raises(ArtifactValidationError, match="missing node"):
        store.publish(
            tenant_id="org-a/project-a",
            document_id="doc-1",
            version=1,
            nodes=[{"node_id": "n1", "label": "A"}],
            edges=[{"source_node_id": "n1", "target_node_id": "missing"}],
        )


def test_failed_publish_keeps_previous_version_readable(tmp_path, monkeypatch):
    store = ArtifactStore(tmp_path / "kg")
    store.publish("org-a/project-a", "doc-1", 1, [{"node_id": "n1"}], [])
    monkeypatch.setattr(store, "_write_json", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk")))

    with pytest.raises(OSError, match="disk"):
        store.publish("org-a/project-a", "doc-1", 2, [{"node_id": "n2"}], [])

    assert (tmp_path / "kg" / "org-a/project-a/doc-1/v1/nodes.json").exists()
```

### Step 2: Run the tests and verify failure

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_artifact_store.py
```

Expected: FAIL because `ArtifactStore` does not exist.

### Step 3: Implement artifact publishing

Expose:

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PublishedArtifact:
    relative_path: str
    manifest_sha256: str
    node_count: int
    edge_count: int


class ArtifactValidationError(ValueError):
    pass


class ArtifactStore:
    def __init__(self, base_dir: str | Path): ...
    def publish(self, tenant_id: str, document_id: str, version: int,
                nodes: list[dict], edges: list[dict]) -> PublishedArtifact: ...
    def validate(self, relative_path: str, expected_manifest_sha256: str | None = None) -> dict: ...
```

Implementation requirements:

- Reject empty/unsafe tenant or document path components; use resolved paths and ensure they remain under `base_dir`.
- Write to `.staging/<tenant>/<document>/<UUID>` on the same filesystem as the final directory.
- Write `nodes.json`, `edges.json`, and `manifest.json`; flush and `os.fsync()` each file before renaming.
- Manifest contains `document_id`, `tenant_id`, `schema_version`, `node_count`, `edge_count`, SHA-256 for both payloads, and creation time.
- Validate every edge source/target against the node ID set before writing.
- Publish with `Path.replace()` only after all files exist; never overwrite an existing version directory.
- On failure, delete only the staging directory; never delete the prior active version.

Implement `KgMetadataStore` with these exact methods:

```python
class KgMetadataStore:
    def __init__(self, db_path: str | Path): ...
    def allocate_version(self, context: AccessContext, document_id: str) -> int: ...
    def register_ready(self, context: AccessContext, document_id: str, version: int,
                       artifact: PublishedArtifact) -> None: ...
    def activate(self, context: AccessContext, document_id: str, version: int) -> None: ...
    def active(self, context: AccessContext, document_id: str) -> dict | None: ...
    def reconcile(self, artifact_store: ArtifactStore) -> dict: ...
```

`activate` must mark the prior active version obsolete and the new version active in one transaction. `reconcile` must mark DB records whose manifest is missing/mismatched unavailable and must not expose filesystem orphan directories.

### Step 4: Replace direct worker writes

Replace `backend/worker.py:1081-1090` direct `open()` calls with:

```python
version = kg_metadata_store.allocate_version(context, document_id)
artifact = artifact_store.publish(
    context.tenant_id,
    document_id,
    version,
    list(all_entities.values()),
    all_edges,
)
kg_metadata_store.register_ready(context, document_id, version, artifact)
kg_metadata_store.activate(context, document_id, version)
```

The caller must supply the same `AccessContext` used for the task. Do not derive tenant or document paths from an untrusted filename.

Update `kg_store.load_all_kg_graphs()` to read only validated active metadata when a database is configured; retain the existing flat/version JSON path only for pre-migration compatibility tests.

### Step 5: Run focused KG tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_artifact_store.py tests/test_kg_indexed_recall.py tests/test_phase4.py::TestTenantKG tests/test_runtime_recovery.py
```

Expected: new atomic publishing tests pass and existing KG loading/recovery tests remain passing.

### Step 6: Commit

```bash
git add backend/persistence/artifact_store.py backend/persistence/kg_metadata_store.py backend/tests/test_persistence_artifact_store.py backend/worker.py backend/kg_store.py backend/routes/query.py
 git commit -m "feat(storage): publish knowledge graph artifacts atomically"
```

---

## Task 8: Scope graph, health, catalog, export, backup and lifecycle consumers

**Files:**
- Create: `backend/tests/test_persistence_consumers.py`
- Modify: `backend/routes/graph.py:32-168`
- Modify: `backend/routes/health.py:72-166`
- Modify: `backend/services/catalog.py`
- Modify: `backend/services/quality.py`
- Modify: `backend/services/kg_exporter.py`
- Modify: `backend/services/backup.py:24-130`
- Modify: `backend/services/lifecycle.py`

### Step 1: Write failing consumer tests

```python

def test_graph_endpoint_excludes_tombstoned_document(client, seeded_state):
    seeded_state.delete_document("org-a/project-a", "doc-deleted")

    response = client.get("/api/v1/graph/all", headers={"X-Project-Id": "project-a"})

    assert response.status_code == 200
    assert all(item["id"] != "d0_n-deleted" for item in response.json()["nodes"])
    assert all(item["id"] != "doc-deleted" for item in response.json()["documents"])


def test_catalog_and_export_use_active_scoped_versions(client, seeded_state):
    seeded_state.create_active_document("doc-a", tenant="org-a/project-a")
    seeded_state.create_active_document("doc-b", tenant="org-b/project-b")

    catalog = client.get("/api/v1/catalog", headers={"X-Project-Id": "project-a"})
    exported = client.get("/api/v1/export/kg", headers={"X-Project-Id": "project-a"})

    assert catalog.status_code == 200
    assert catalog.json()["summary"]["total_documents"] == 1
    assert b"doc-b" not in exported.content
```

Add a backup test asserting `state.sqlite3`, manifest files, and the migration backup directory are listed while `.env` and API keys are not.

### Step 2: Run tests and verify failure

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_consumers.py
```

Expected: FAIL because consumers still scan every `output/kg` directory and ignore tombstones/scope.

### Step 3: Route consumers through Stores

For each consumer:

- Accept `Request` where the route is HTTP-facing and call `context_from_request(request)`.
- Call `DocumentStore.list(context)` to obtain visible documents.
- Resolve each document’s `KgMetadataStore.active(context, document_id)` and call `ArtifactStore.validate(...)` before reading JSON.
- Never scan arbitrary `output/kg/*` directories to determine visibility.
- Preserve existing response shapes and export formats.
- In health checks, report counts from active Store records; a missing/invalid active artifact makes readiness degraded, not a successful zero count.

Update backup configuration so the manifest includes:

```python
"state_db": {"path": "output/state.sqlite3", "strategy": "sqlite_snapshot"},
"migration_backups": {"path": "output/migrations/backups", "strategy": "copy"},
"kg": {"path": "output/kg", "strategy": "active_artifacts"},
```

The backup exclusion list must still exclude `.env`, `.env.*` credentials, and API-token-bearing files.

### Step 4: Run consumer and regression tests

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_consumers.py tests/test_phase2.py tests/test_phase4.py
```

Expected: new consumer scope tests pass. The known five `test_phase2.py` fixture failures may remain and must be reported separately; no new failures are allowed outside that baseline.

### Step 5: Commit

```bash
git add backend/tests/test_persistence_consumers.py backend/routes/graph.py backend/routes/health.py backend/services/catalog.py backend/services/quality.py backend/services/kg_exporter.py backend/services/backup.py backend/services/lifecycle.py
 git commit -m "feat(storage): scope graph and operational consumers"
```

---

## Task 9: Remove JSON writes, document compatibility, and complete verification

**Files:**
- Modify: `backend/routes/ingest.py`
- Modify: `backend/routes/__init__.py`
- Modify: `backend/kg_store.py`
- Modify: `backend/services/backup.py`
- Modify: `backend/CLAUDE.md`
- Modify: `.lra/feature-list.json`
- Modify: `.lra/progress.txt`
- Create: `backend/tests/test_f005_regression.py`

### Step 1: Write final regression tests

```python

def test_restart_preserves_done_task_and_stales_running_task(tmp_path):
    ...


def test_json_files_are_not_written_by_task_or_document_store(tmp_path):
    ...


def test_concurrent_version_allocation_returns_unique_versions(tmp_path):
    ...


def test_deleted_document_cannot_be_loaded_into_grounded_graph(tmp_path):
    ...
```

The test implementations must use `tmp_path`, real subprocesses or threads where concurrency is claimed, and assert the database rows/artifact files rather than only mocking function calls. The restart test must serialize one `done` task and one `running` task, invoke the startup migration twice, then assert `done` remains queryable and `running` becomes `failed + lifecycle_status=stale`.

### Step 2: Run final regression tests and inspect direct JSON writes

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_f005_regression.py
.venv/Scripts/python.exe -m ruff check persistence routes/ingest.py routes/__init__.py routes/documents.py routes/graph.py routes/health.py kg_store.py worker.py services/catalog.py services/quality.py services/kg_exporter.py services/backup.py services/lifecycle.py
```

Also run a source search:

```bash
cd backend
.venv/Scripts/python.exe -c "from pathlib import Path; import re; roots=[Path('routes'),Path('services'),Path('worker.py'),Path('kg_store.py')]; hits=[]; [hits.extend((p, i+1, line.strip()) for i,line in enumerate(p.read_text(encoding='utf-8').splitlines()) if re.search(r'open\\(.*(tasks_store|docs_store|nodes\\.json|edges\\.json|versions\\.json)', line)) for p in ([root] if root.is_file() else root.rglob('*.py'))]; print(*hits, sep='\\n')"
```

Expected: no production task/document writes outside the persistence package; remaining JSON reads must be explicitly marked as migration or compatibility reads.

### Step 3: Update documentation and feature state

Update `backend/CLAUDE.md` so these statements are true:

- `output/state.sqlite3` is the runtime source for task/document/KG metadata.
- `output/kg/**/vN` contains immutable JSON payloads referenced by active SQLite metadata.
- `tasks_store.json` and `docs_store.json` are migration/backup inputs only.
- `TaskStatus` remains the four-value public contract; stale is internal recovery metadata.

Only after all tests and review gates pass, update `.lra/feature-list.json` F005:

```json
{
  "status": "completed",
  "completed_at": "2026-09-19",
  "session": 3,
  "notes": "SQLite task/document/KG metadata, idempotent startup migration, stale recovery, tenant-scoped Stores, tombstone deletion, and atomic KG artifact publication verified by backend tests. Known pre-existing phase2 fixture failures remain separately recorded."
}
```

Append the exact test commands and outcomes to `.lra/progress.txt`; do not claim the full suite is green while the five known fixture failures remain.

### Step 4: Run the complete verification set

```bash
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_persistence_context.py tests/test_persistence_sqlite.py tests/test_persistence_task_store.py tests/test_persistence_document_store.py tests/test_persistence_migration.py tests/test_persistence_artifact_store.py tests/test_persistence_api.py tests/test_persistence_consumers.py tests/test_f005_regression.py
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m bandit -r . -x tests,.venv,output,uploads
```

Expected:

- All new F005 tests pass.
- The full suite has no new failures compared with the recorded `425 passed / 5 failed` baseline.
- Ruff passes for all F005 files. Existing unrelated repository warnings must be listed, not silently ignored.
- Bandit has no new high-severity finding.

### Step 5: Request code review before marking complete

Run the Python reviewer against the complete diff. Review must specifically inspect:

1. Every Store query has tenant and owner predicates unless it is an explicitly named startup/system operation.
2. No public `TaskStatus` change occurred.
3. Artifact paths are resolved beneath the configured KG root.
4. JSON migration never treats corruption as an empty database.
5. Tombstoned records cannot be loaded by graph/query/catalog/export.
6. A failed publish leaves the prior active version readable.

Fix every confirmed correctness/security issue, rerun the affected focused test and full verification command, then commit:

```bash
git add backend .lra docs/superpowers/plans/2026-09-19-f005-state-persistence.md
git commit -m "feat(storage): complete F005 persistent state migration"
```

---

## Completion gate

F005 may be marked completed only when all of the following have concrete test output:

- `tasks`, `documents`, `kg_versions`, and `tombstones` exist in SQLite with non-null scope columns.
- Re-running startup migration does not duplicate data and corrupted source JSON is preserved and reported.
- A completed task remains queryable after process/module restart; an in-flight task becomes `failed` with internal `stale` lifecycle metadata.
- `duration_seconds` works after reload because timestamps are parsed back into timezone-aware datetimes.
- Task/document/active-KG metadata updates are transactional at the application boundary.
- KG nodes/edges are published through staging + manifest + atomic rename; previous active versions survive failed publishes.
- Deletion checks scoped existence first, writes a tombstone, and does not delete neighboring documents with similar IDs.
- Graph, query, catalog, quality, export, health, backup, and lifecycle consumers use active scoped metadata.
- F003/F004 regression tests pass and the five pre-existing phase2 fixture failures are unchanged and separately documented.
- Reviewer confirms no new direct JSON state writes, no scope bypass, no API wire break, and no secret exposure.

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-19-f005-state-persistence.md`. Two execution options:

1. **Subagent-Driven (recommended):** dispatch a fresh subagent per task, run two-stage review between tasks, and checkpoint after each commit.
2. **Inline Execution:** execute the tasks in this session using the executing-plans workflow with review checkpoints.

Do not start implementation until one execution option is selected and the implementation session begins from Task 1.
