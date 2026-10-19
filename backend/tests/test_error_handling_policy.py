"""错误处理策略守卫 —— ruff 开启前的预检，同时防止后续回流。"""
import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
CLI_T20_EXEMPT = {
    "pipeline.py", "run_evaluation.py", "agentic_rag_mvp.py",
    "build_indices.py", "scripts/check_imports.py",
    # Task 5 新增的一次性运维 CLI（含 __main__ 守卫，全仓零处 import）。
    # 与 scripts/check_imports.py 同属「文件角色即 CLI」一类，故同样豁免 T20。
    "scripts/purge_log_secrets.py",
}
# These research modules are also imported as libraries. Only their command
# entrypoint bodies may print; their helpers have no file-wide exemption.
RESEARCH_CLI_ENTRYPOINTS = {
    "research/common_evaluate_summary.py", "research/common_evaluation_packets.py",
    "research/common_protection.py", "research/common_resource_audit.py",
    "research/common_scope_audit.py", "research/common_three_arm.py",
    "research/development_isolation.py", "research/development_profile_cli.py",
    "research/development_run_authorized.py", "research/development_summarize.py",
}


def _library_print_lines(tree, registered_cli=False):
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    allowed_roots = set()
    if registered_cli:
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main":
                # Defaults, annotations and decorators execute during import.
                allowed_roots.update(child for child in node.body if not isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ))
            elif isinstance(node, ast.If) and ast.dump(node.test) == ast.dump(
                ast.parse("__name__ == '__main__'", mode="eval").body
            ):
                # The else branch runs during import and is library code.
                allowed_roots.update(child for child in node.body if not isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print"):
            continue
        parent = parents.get(node)
        while parent is not None:
            if parent in allowed_roots:
                break
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                parent = None
                break
            parent = parents.get(parent)
        if parent is None:
            yield node.lineno
# 被跳过的目录。注意 .venv 下有近 2 万个 .py —— 必须**在遍历时剪枝**，
# 而不是 rglob 出来再过滤（后者每个测试多走 2 万次 stat）。
_SKIP_DIRS = {".venv", "output", "__pycache__", "uploads", "node_modules", ".pytest-tmp"}


def _sources():
    """yield (Path, rel_posix) —— 只含 backend 自身的库/路由代码，不含 tests。"""
    stack = [BACKEND]
    while stack:
        d = stack.pop()
        for entry in d.iterdir():
            if entry.is_dir():
                # tests 已排除在源码范围外，须在遍历前剪枝其生成目录树。
                if entry == BACKEND / "tests":
                    continue
                if entry.name in _SKIP_DIRS or entry.name.startswith("."):
                    continue
                stack.append(entry)
            elif entry.suffix == ".py":
                rel = str(entry.relative_to(BACKEND)).replace("\\", "/")
                if rel.startswith("tests/"):
                    continue
                yield entry, rel


def test_library_modules_have_no_print():
    """Library stdout is forbidden; registered research CLIs allow entrypoints only."""
    offenders = []
    for path, rel in _sources():
        if rel in CLI_T20_EXEMPT:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        offenders.extend(f"{rel}:{line}" for line in _library_print_lines(tree, rel in RESEARCH_CLI_ENTRYPOINTS))
    assert not offenders, f"库代码仍有 print()：{offenders}"


def test_cli_exemptions_are_load_bearing():
    """豁免清单不得变成垃圾桶：列出的文件必须真的含 print。"""
    for rel in CLI_T20_EXEMPT:
        src = (BACKEND / rel).read_text(encoding="utf-8")
        assert "print(" in src, f"{rel} 已无 print，应从豁免清单移除"
    for rel in RESEARCH_CLI_ENTRYPOINTS:
        tree = ast.parse((BACKEND / rel).read_text(encoding="utf-8"))
        guards = [n for n in tree.body if isinstance(n, ast.If) and ast.dump(n.test) == ast.dump(ast.parse("__name__ == '__main__'", mode="eval").body)]
        assert guards, f"{rel} must retain an executable CLI guard"
        assert any(isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print" for n in ast.walk(tree)), rel


def test_no_bare_except_outside_tests():
    offenders = []
    for path, rel in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, f"存在裸 except：{offenders}"


def test_every_ble001_noqa_has_a_reason():
    """每条 # noqa: BLE001 必须带 `#` 理由，否则豁免无从审计。

    判定用**双空格分隔**的形态约束，而不是数字符数：
    规范写法是 `# noqa: <码表>  # 理由`（两个空格 + 井号）。理由文本内部
    可能含 `#`（如引用 issue 号），也可能不含 —— 数 `#` 个数会把两者都判错
    （计划初版的 `count("#") < 2` 对合规行恒为 1，会让**全部** 114 行误报）。

    BLE001 可与其它规则码并列（如 S110 描述 try/except/pass），且**顺序不限** ——
    本函数入口已按「行内含 BLE001」过滤，故正则只需校验整体形态。
    不要写成把 BLE001 钉死在码表末尾的版本
    （`(?:\s*\w+,)*\s*BLE001\s{2,}#`）—— 那样 `# noqa: BLE001, S110  # 理由`
    会被误判为「缺理由」。
    """
    import re

    pattern = re.compile(r"#\s*noqa:\s*[A-Z]+\d+(?:\s*,\s*[A-Z]+\d+)*\s{2,}#\s*\S")
    offenders = []
    for path, rel in _sources():
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            if "noqa" not in line or "BLE001" not in line:
                continue
            if not pattern.search(line):
                offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert not offenders, (
        "# noqa: BLE001 缺少理由（应为 `# noqa: BLE001  # 理由`）：\n"
        + "\n".join(offenders)
    )


def test_worker_uses_structlog():
    """worker.py 必须走 structlog，否则绕过脱敏链。"""
    src = (BACKEND / "worker.py").read_text(encoding="utf-8")
    assert "logging.getLogger" not in src
    assert "get_logger" in src
