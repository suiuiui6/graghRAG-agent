"""R7 controlled local-file prototype, not a Chroma compatibility adapter.

Fixed little-endian f64 vectors; finite nonzero vectors only. Max 4096 dimensions,
1000 batch/k, 10000 records, 1MiB individual payload, 100MiB snapshots.
No arbitrary SQL, model loading, pickle, remote files or external DB admission.
"""
from contextlib import closing
import hashlib
import hmac
import json
import math
from pathlib import Path
import sqlite3
import tempfile

import numpy as np

MAX_ROWS = 10000
MAX_BYTES = 1048576
MAX_SNAPSHOT = 100 * 1048576
SCHEMA = "CREATE TABLE records(id TEXT PRIMARY KEY, source TEXT NOT NULL, text TEXT NOT NULL, metadata TEXT NOT NULL, vector BLOB NOT NULL, dimension INTEGER NOT NULL)"
CONFIG = "CREATE TABLE config(dimension INTEGER NOT NULL)"


def _connect(path, *, readonly=False, timeout=0.2):
    """Private connection factory: failure to enforce any setting fails closed."""
    if not math.isfinite(timeout) or not 0 <= timeout <= 10:
        raise ValueError("连接超时超出范围")
    uri = Path(path).resolve().as_uri() + ("?mode=ro" if readonly else "?mode=rw")
    con = sqlite3.connect(uri, uri=True, timeout=timeout)
    try:
        if sqlite3.sqlite_version_info < (3, 53, 2):
            raise RuntimeError("SQLite版本未达安全基线")
        for setting, value in [(sqlite3.SQLITE_DBCONFIG_DEFENSIVE, True), (sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA, False), (sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION, False)]:
            con.setconfig(setting, value)
            if con.getconfig(setting) != value:
                raise RuntimeError("连接硬化失败")
        con.execute("PRAGMA trusted_schema=OFF")
        con.execute("PRAGMA foreign_keys=ON")
        if con.execute("PRAGMA trusted_schema").fetchone()[0] != 0 or con.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("连接PRAGMA硬化失败")
        for category, ceiling in [(sqlite3.SQLITE_LIMIT_LENGTH, MAX_BYTES), (sqlite3.SQLITE_LIMIT_SQL_LENGTH, 65536), (sqlite3.SQLITE_LIMIT_COLUMN, 32), (sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 32), (sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 8), (sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, 32), (sqlite3.SQLITE_LIMIT_ATTACHED, 0)]:
            con.setlimit(category, ceiling)
            if con.getlimit(category) > ceiling:
                raise RuntimeError("连接资源限制失败")
        return con
    except BaseException:
        con.close()
        raise


def _dimension(value):
    if type(value) is not int or not 1 <= value <= 4096:
        raise ValueError("维度必须为1至4096整数")
    return value


def _text(value):
    if type(value) is not str or len(value.encode("utf-8")) > MAX_BYTES:
        raise ValueError("文本类型或大小无效")
    return value


def _vector(value, dimension):
    try:
        vector = np.asarray(value, dtype="<f8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("向量格式无效") from exc
    if vector.shape != (dimension,) or not np.isfinite(vector).all():
        raise ValueError("向量维度或有限性无效")
    scale = np.max(np.abs(vector))
    if scale == 0:
        raise ValueError("原型拒绝零向量")
    scaled = vector / scale
    unit = scaled / np.sqrt(np.dot(scaled, scaled))
    if not np.isfinite(unit).all():
        raise ValueError("向量归一化结果非有限")
    return vector, unit


def _schema(con, expected=None):
    definitions = dict(con.execute("SELECT name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%'"))
    if definitions != {"records":SCHEMA, "config":CONFIG}:
        raise ValueError("数据库schema无效")
    dimensions = con.execute("SELECT dimension FROM config").fetchall()
    if len(dimensions) != 1:
        raise ValueError("维度配置无效")
    dimension = _dimension(dimensions[0][0])
    if expected is not None and dimension != expected:
        raise ValueError("持久化维度不匹配")
    if con.execute("SELECT COUNT(*) FROM records").fetchone()[0] > MAX_ROWS:
        raise ValueError("数据库记录上限超出")
    return dimension


class Store:
    def __init__(self, path, dimension=3, timeout=0.2):
        self.dimension = _dimension(dimension)
        self.path = Path(path).resolve()
        self.timeout = timeout
        created = False
        try:
            with self.path.open("xb"):
                created = True
        except FileExistsError:
            pass
        try:
            with closing(_connect(self.path, timeout=timeout)) as con:
                if created:
                    if con.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
                        raise RuntimeError("WAL启用失败")
                    with con:
                        con.execute(SCHEMA)
                        con.execute(CONFIG)
                        con.execute("INSERT INTO config VALUES (?)", (dimension,))
                _schema(con, dimension)
        except BaseException:
            if created:
                self.path.unlink(missing_ok=True)
            raise

    def add(self, records):
        if type(records) is not list or not 1 <= len(records) <= 1000:
            raise ValueError("批次必须含1至1000记录")
        batch = []
        for row in records:
            vector, _ = _vector(row["vector"], self.dimension)
            try:
                if type(row["metadata"]) is not dict:
                    raise ValueError("metadata必须为对象")
                metadata = json.dumps(row["metadata"], ensure_ascii=False, allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise ValueError("metadata JSON无效") from exc
            item = (_text(row["id"]), _text(row["source"]), _text(row["text"]), _text(metadata), vector.tobytes(), self.dimension)
            if sum(len(x.encode("utf-8")) if isinstance(x,str) else len(x) if isinstance(x,bytes) else 8 for x in item) > MAX_BYTES-128:
                raise ValueError("记录大小超出限制")
            batch.append(item)
        with closing(_connect(self.path, timeout=self.timeout)) as con, con:
            con.execute("BEGIN IMMEDIATE")
            if con.execute("SELECT COUNT(*) FROM records").fetchone()[0]+len(batch) > MAX_ROWS:
                raise ValueError("记录上限超出")
            con.executemany("INSERT INTO records VALUES (?,?,?,?,?,?)", batch)

    def get(self, id):
        with closing(_connect(self.path, readonly=True, timeout=self.timeout)) as con:
            row = con.execute("SELECT id,source,text,metadata,vector,dimension FROM records WHERE id=?", (_text(id),)).fetchone()
        return None if row is None else {"id":row[0],"source":row[1],"text":row[2],"metadata":json.loads(row[3]),"vector":list(np.frombuffer(row[4],dtype="<f8"))}

    def delete(self, id):
        with closing(_connect(self.path, timeout=self.timeout)) as con, con:
            con.execute("DELETE FROM records WHERE id=?", (_text(id),))

    def delete_source(self, source):
        with closing(_connect(self.path, timeout=self.timeout)) as con, con:
            con.execute("DELETE FROM records WHERE source=?", (_text(source),))

    def search(self, vector, k, source=None):
        if type(k) is not int or not 1 <= k <= 1000:
            raise ValueError("k必须为1至1000整数")
        _, query = _vector(vector, self.dimension)
        with closing(_connect(self.path, readonly=True, timeout=self.timeout)) as con:
            if source is None:
                rows = con.execute("SELECT id,vector,dimension FROM records LIMIT 10001").fetchall()
            else:
                rows = con.execute("SELECT id,vector,dimension FROM records WHERE source=? LIMIT 10001", (_text(source),)).fetchall()
        if len(rows) > MAX_ROWS:
            raise ValueError("搜索规模超出限制")
        hits = []
        for id, blob, dimension in rows:
            if dimension != self.dimension or len(blob) != self.dimension*8:
                raise ValueError("持久化向量格式无效")
            _, unit = _vector(np.frombuffer(blob, dtype="<f8"), self.dimension)
            cosine = float(np.dot(query, unit))
            if not math.isfinite(cosine) or not -1-1e-12 <= cosine <= 1+1e-12:
                raise ValueError("派生余弦得分无效")
            score = (max(-1., min(1., cosine))+1)/2
            hits.append({"id":id,"score":score})
        return sorted(hits, key=lambda hit:(-hit["score"],hit["id"]))[:k]

    def backup(self, snapshot):
        snapshot = Path(snapshot).resolve()
        with snapshot.open("xb"):
            pass
        try:
            with closing(_connect(self.path, readonly=True, timeout=self.timeout)) as source, closing(_connect(snapshot, timeout=self.timeout)) as dest:
                source.backup(dest)
                _schema(dest, self.dimension)
                if dest.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise ValueError("备份完整性检查失败")
            if snapshot.stat().st_size > MAX_SNAPSHOT:
                raise ValueError("快照超出大小限制")
            with snapshot.open("rb") as stream:
                content = stream.read(MAX_SNAPSHOT+1)
            if len(content) > MAX_SNAPSHOT:
                raise ValueError("快照超出大小限制")
            return {"sha256":hashlib.sha256(content).hexdigest(), "size":len(content)}
        except BaseException:
            snapshot.unlink(missing_ok=True)
            raise

    @staticmethod
    def restore(snapshot, target, *, sha256, size):
        """Trusted caller-held identity only; identity is checked before SQLite parsing.

        Copy verified bytes into a private staging file to avoid source hash/open
        races. Only create a fresh destination; never overwrite an existing one.
        """
        target = Path(target).resolve()
        if target.exists():
            raise FileExistsError("恢复目标已存在")
        if type(size) is not int or not 0 < size <= MAX_SNAPSHOT or type(sha256) is not str:
            raise ValueError("可信快照身份无效")
        with Path(snapshot).open("rb") as stream:
            content = stream.read(size+1)
        if len(content) != size or not hmac.compare_digest(hashlib.sha256(content).hexdigest(), sha256):
            raise ValueError("快照尺寸或摘要不匹配")
        with tempfile.TemporaryDirectory(prefix="r7-restore-", dir=target.parent) as directory:
            stage = Path(directory)/"verified.sqlite"
            stage.write_bytes(content)
            with closing(_connect(stage, readonly=True)) as source:
                _schema(source)
                if source.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise ValueError("快照完整性检查失败")
                with target.open("xb"):
                    pass
                try:
                    with closing(_connect(target)) as dest:
                        source.backup(dest)
                        _schema(dest)
                except BaseException:
                    target.unlink(missing_ok=True)
                    raise
