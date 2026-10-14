"""Prepare physical research copies without importing or starting copied code.

This is a stopped-source capture gate, not an online SQLite backup. A caller
must launch the dedicated Python with -I -S -B and explicitly add only the
snapshot backend and dedicated site-packages; never call site.addsitedir.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
from typing import Iterable


def _absolute(path: Path | str) -> Path:
    return Path(os.path.abspath(path))


def _excluded(name: str) -> bool:
    lower = name.lower()
    return (lower.startswith((".env", ".pytest"))
            or lower in {"logs", "log", "__pycache__", "research-isolation-tests"}
            or lower.endswith((".pyc", ".pyo")) or ".log" in lower)


def _check_path(path: Path) -> None:
    """lstat every existing ancestor before resolving or opening anything."""
    for ancestor in reversed((path, *path.parents)):
        try:
            info = ancestor.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("unsafe symlink/reparse/junction path")
        if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise ValueError("unsafe hardlink path")
        if not stat.S_ISREG(info.st_mode) and not stat.S_ISDIR(info.st_mode):
            raise ValueError("unsupported filesystem object")


def _within(base: Path, path: Path) -> None:
    if not path.is_relative_to(base):
        raise ValueError("path escapes containment")
    _check_path(path)


def safe_files(base: Path | str, paths: Iterable[Path | str]) -> list[Path]:
    """Return sorted regular files; skip excluded names before lstat/open."""
    base = _absolute(base)
    _check_path(base)
    found: set[Path] = set()

    def visit(path: Path) -> None:
        if not path.is_relative_to(base):
            raise ValueError("path escapes containment")
        if any(_excluded(part) for part in path.relative_to(base).parts):
            return
        _within(base, path)
        if not path.exists():
            return
        if path.is_dir():
            for child in sorted(path.iterdir()):
                visit(child)
        else:
            found.add(path)

    for supplied in paths:
        candidate = Path(supplied)
        visit(_absolute(candidate if candidate.is_absolute() else base / candidate))
    return sorted(found)


def _identity(info: os.stat_result) -> dict:
    return {"device": info.st_dev, "inode": info.st_ino, "links": info.st_nlink,
            "size": info.st_size, "mtime_ns": info.st_mtime_ns}


def _fingerprint(path: Path) -> dict:
    _check_path(path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("expected regular file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if _identity(opened) != _identity(before):
            raise ValueError("source drift while opening")
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        after = os.fstat(stream.fileno())
    _check_path(path)
    if _identity(before) != _identity(after) or _identity(before) != _identity(path.stat()):
        raise ValueError("source drift while hashing")
    return {**_identity(before), "sha256": digest.hexdigest()}


def copy_verified(source: Path | str, target: Path | str) -> dict:
    """Exclusive physical copy with stable source hash and distinct identity."""
    source, target = _absolute(source), _absolute(target)
    if any(_excluded(part) for part in (*source.parts, *target.parts)):
        raise ValueError("excluded secret/log/bytecode path")
    _check_path(target)
    if target.exists():
        raise ValueError("destination already exists")
    before = _fingerprint(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    _check_path(target)
    with source.open("rb") as incoming, target.open("xb") as outgoing:
        opened = _identity(os.fstat(incoming.fileno()))
        if opened != {key: before[key] for key in opened}:
            raise ValueError("source drift before copying")
        for block in iter(lambda: incoming.read(1024 * 1024), b""):
            outgoing.write(block)
        outgoing.flush()
        os.fsync(outgoing.fileno())
    after, destination = _fingerprint(source), _fingerprint(target)
    if before != after or before["sha256"] != destination["sha256"]:
        raise ValueError("source drift or copy hash mismatch")
    if (before["device"], before["inode"]) == (destination["device"], destination["inode"]):
        raise ValueError("copy is not physically independent")
    return {"source": str(source), "target": str(target), "before": before,
            "after": after, "destination": destination}


def _pth_safe(path: Path, site_root: Path) -> None:
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or entry.startswith(("import ", "import\t")):
            continue  # Never activated: required launcher has -S.
        windows = PureWindowsPath(entry)
        if Path(entry).is_absolute() or windows.drive or windows.root:
            raise ValueError("unsafe absolute pth reference")
        candidate = _absolute(path.parent / entry)
        if not candidate.is_relative_to(site_root):
            raise ValueError("unsafe escaping pth reference")
        _check_path(candidate)


def _plan(root: Path, base_python: Path, run: Path) -> list[tuple[Path, Path]]:
    backend = root / "backend"
    _check_path(backend)
    _check_path(base_python)
    base = base_python.parent
    if (base_python.name.lower() != "python.exe" or not base_python.is_file()
            or (base / "pyvenv.cfg").exists() or (base.parent / "pyvenv.cfg").exists()
            or not (base / "Lib").is_dir()):
        raise ValueError("base_python must be actual base python.exe, not a venv launcher")
    _check_path(base / "python312.dll")
    if not (base / "python312.dll").is_file():
        raise ValueError("required python312.dll is missing")
    # Only root files and explicitly selected directories, never the whole backend.
    code = []
    for child in backend.iterdir():
        if (not _excluded(child.name)
                and (child.suffix.lower() == ".py" or child.name.lower() in {"uv.lock", "pyproject.toml"})):
            _check_path(child)
            if child.is_file():
                code.append(child)
    for name in ("routes", "services", "middleware", "bot", "migrations", "research"):
        code.extend(path for path in safe_files(backend, [backend / name]) if path.suffix.lower() == ".py")
    domain = backend / "config" / "domain_dict.yaml"
    _within(backend, domain)
    if not domain.is_file():
        raise ValueError("required config/domain_dict.yaml regular file is missing")
    code.append(domain)
    output = backend / "output"
    assets: list[Path] = []
    for name in ("vectordb", "runtime", "kg", "mineru", "embedding_cache"):
        assets.extend(safe_files(backend, [output / name]))
    for name in ("docs_store.json", "runtime_cache.sqlite3", "rewrite-cache.sqlite3", "runtime.db"):
        main = output / name
        assets.extend(safe_files(backend, [main, Path(str(main) + "-wal"), Path(str(main) + "-shm"), Path(str(main) + "-journal")]))
    for source in assets:
        lower = source.name.lower()
        if source.stat().st_size and lower.endswith(("-wal", "-journal")):
            kind = "WAL" if lower.endswith("-wal") else "rollback journal"
            raise ValueError(f"nonempty {kind}: stop/checkpoint source before capture")
    pairs = [(path, run / "backend" / path.relative_to(backend)) for path in sorted(set(code + assets))]
    runtime = safe_files(base, [base_python, *base.glob("*.dll"), base / "DLLs"])
    # Walk stdlib by immediate child to exclude global site-packages before reading it.
    for child in (base / "Lib").iterdir():
        if child.name.lower() != "site-packages":
            runtime.extend(safe_files(base, [child]))
    pairs.extend((path, run / "python" / path.relative_to(base)) for path in sorted(set(runtime)))
    site = backend / ".venv" / "Lib" / "site-packages"
    _check_path(site)
    if not site.is_dir():
        raise ValueError("project site-packages is missing")
    for path in safe_files(site, [site]):
        if path.suffix.lower() == ".pth":
            _pth_safe(path, site)
        pairs.append((path, run / "python" / "Lib" / "site-packages" / path.relative_to(site)))
    destinations = [destination for _, destination in pairs]
    if len(set(destinations)) != len(destinations):
        raise ValueError("duplicate destination")
    for source, destination in pairs:
        _within(run, destination)
    return sorted(pairs, key=lambda pair: str(pair[1]))


def _write_manifest(run: Path, manifest: dict) -> None:
    path = run / "manifest.json"
    _within(run, path)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def prepare_snapshot(root: Path | str, run_id: str, base_python: Path | str) -> dict:
    """Preflight and capture; failures keep a unique partial tree for inspection.

    No imports, database operations, network calls, or executable launches occur.
    This function alone does not establish or attest a firewall.
    """
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", run_id):
        raise ValueError("invalid run_id")
    root, base_python = _absolute(root), _absolute(base_python)
    _check_path(root)
    run = root / "backend" / "output" / "research-isolation" / run_id
    _within(root, run)
    if run.exists():
        raise ValueError("run directory already exists")
    plan = _plan(root, base_python, run)
    origins = {str(source): _fingerprint(source) for source, _ in plan}
    run.parent.mkdir(parents=True, exist_ok=True)
    _check_path(run)
    run.mkdir()  # Atomic uniqueness gate; never reuse or delete an existing run.
    manifest = {"schema_version": 1, "run_id": run_id, "run_root": str(run),
                "python_executable": str(run / "python" / "python.exe"),
                "status": "copying", "files": [], "origins_before": origins,
                "origins_after": {}, "required_python_flags": ["-I", "-S", "-B"],
                "pth_activation": "DISABLED_BY_MINUS_S",
                "required_sys_path": [str(run / "backend"), str(run / "python" / "Lib" / "site-packages")],
                "site_addsitedir_allowed": False, "firewall_status": "NOT_ESTABLISHED",
                "service_started": False}
    _write_manifest(run, manifest)
    try:
        for source, destination in plan:
            record = copy_verified(source, destination)
            if record["before"] != origins[str(source)]:
                raise ValueError("source drift since preflight")
            manifest["files"].append(record)
        if _plan(root, base_python, run) != plan:
            raise ValueError("source drift in file inventory")
        manifest["origins_after"] = {str(source): _fingerprint(source) for source, _ in plan}
        if manifest["origins_after"] != origins:
            raise ValueError("source drift during snapshot")
        for record in manifest["files"]:
            if _fingerprint(Path(record["target"])) != record["destination"]:
                raise ValueError("destination drift during snapshot")
        inventory = {str(Path(record["target"]).relative_to(run)): record["destination"]["sha256"]
                     for record in manifest["files"]}
        manifest["destination_file_count"] = len(inventory)
        manifest["destination_inventory_sha256"] = hashlib.sha256(
            json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        manifest["status"] = "verified"
        _write_manifest(run, manifest)
        return manifest
    except Exception as error:
        manifest["status"] = "failed"
        manifest["failure_type"] = type(error).__name__
        _write_manifest(run, manifest)
        raise
