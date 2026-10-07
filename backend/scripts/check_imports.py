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
