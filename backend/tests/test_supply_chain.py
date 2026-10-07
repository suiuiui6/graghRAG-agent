# backend/tests/test_supply_chain.py
"""供应链治理回归测试：依赖清单一致性 + 关键模块可导入。"""
from __future__ import annotations

import ast
import importlib.metadata as importlib_metadata
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


def test_requirements_matches_pyproject():
    """requirements 与 pyproject 的依赖集合必须一致（langextract 除外，它是本地路径源）。"""
    py = _pyproject_deps() - {"langextract"}
    req = _requirements_deps()
    assert py == req, f"不一致 —— 仅 pyproject 有: {py - req}；仅 requirements 有: {req - py}"


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

# 绑定「一个 import 根映射到多个 dist」的命名空间根。
# 其余会被静默放过（曾实测 opentelemetry 6/6、google 8/8 未被声明却全部通过）。
# 故此类根必须显式登记，新增即意味着一次人工确认。
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
