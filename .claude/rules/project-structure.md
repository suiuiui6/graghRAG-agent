---
paths:
  - "backend/**/*.py"
---
# 规则：Python 项目结构与存储抽象

> 来源：developer-kit `python/rules/project-structure.md` + `clean-architecture` skill，按本项目现状裁剪。
> 对应 backlog F005（状态持久化）/ D01（存储抽象层）。

## 现状与目标

本项目当前结构已较清晰（`routes/`、`services/`、`middleware/`、`*.py` 组件），但**核心状态仍存在全局单例风险**：`_tasks` / `_docs_store` / `G_grounded` / `_agent`（双检锁）。这是「可运行不可交付」的总根，也是多进程/重启丢状态、多用户无法隔离的来源。

## 分层职责（FastAPI 场景）

| 层 | 文件 | 职责 |
|----|------|------|
| 路由 | `routes/*.py` | 参数解析、响应格式化，**不放业务逻辑** |
| Schema | `models.py` / `schema.py` | Pydantic 请求/响应模型 |
| 服务 | `services/*.py` | 业务编排、事务管理 |
| 存储 | `stores/` 或 `services/*_store.py` | 数据访问抽象，统一读写接口 |
| 基础设施 | `middleware/`、`config.py` | 认证、租户、限流、配置 |

## 存储抽象（关键改造）

- JSON 全量读写**必须收敛到统一存储模块**，禁止散落在路由/任务逻辑里
- 切换 SQLite 时只改底层实现，上层接口不变：

```python
# ✅ 好：统一存储接口
class TaskStore(Protocol):
    def get(self, task_id: str) -> Task | None: ...
    def save(self, task: Task) -> None: ...
    def update_status(self, task_id: str, status: str) -> None: ...

# 调用方
store: TaskStore = get_task_store()   # 环境变量切换 json | sqlite
store.update_status(task_id, "committing")
```

- 图谱写入用**临时目录 + 原子切换**，禁止线程锁 + 直接覆写（进程中断会损坏文件）
- 删除用 **tombstone**（先标记失效，再异步清理），禁止按文件名前缀推断删除

## 文件组织规则

- 一个文件一个职责，模块名用 `snake_case`
- `__init__.py` 控制公开导出，避免重型 import
- 测试镜像 `tests/` 结构，`conftest.py` 放共享 fixture
- 依赖用 `pyproject.toml`（当前项目尚无，F001 需补锁文件）
