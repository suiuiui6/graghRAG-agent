import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from store import Store


def record(id, vector=(1., 0., 0.), source="s"):
    return {"id": id, "source": source, "text": "中文正文", "metadata": {"x": "'"}, "vector": vector}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "records.sqlite"
        try:
            self.store = Store(self.path)
        except NotImplementedError as exc:
            self.fail(str(exc))

    def test_core_atomic_parameterized_persistence(self):
        evil = "x'); DROP TABLE records; --"
        self.store.add([record(evil, source=evil), record("ordinary")])
        self.assertEqual(self.store.get(evil)["source"], evil)
        self.assertEqual(self.store.get(evil)["metadata"], {"x": "'"})
        with self.assertRaises(Exception):
            self.store.add([record("new"), record("ordinary")])
        self.assertIsNone(self.store.get("new"))
        code = "from store import Store; import sys; s=Store(sys.argv[1]); assert s.get(sys.argv[2])['text']=='中文正文'; print('reopen-ok')"
        p = subprocess.run([sys.executable, "-X", "utf8", "-c", code, str(self.path), evil], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), "reopen-ok")
        self.store.delete_source(evil)
        self.assertIsNone(self.store.get(evil))
        self.assertIsNotNone(self.store.get("ordinary"))
        self.store.delete("ordinary")
        self.assertIsNone(self.store.get("ordinary"))

    def test_scores_prefilter_ties_limits(self):
        self.store.add([record("a"), record("b", (0, 1, 0)), record("c", (-1, 0, 0)), record("d", source="other"), record("aa")])
        hits = self.store.search((1, 0, 0), 5)
        self.assertEqual([x["id"] for x in hits], ["a", "aa", "d", "b", "c"])
        self.assertEqual([x["score"] for x in hits], [1, 1, 1, .5, 0])
        self.assertEqual(self.store.search((1, 0, 0), 1, source="other")[0]["id"], "d")
        self.assertEqual(self.store.search((1, 0, 0), 2, source="absent"), [])
        for k in [0, -1, True, 1001, 1.2]:
            with self.subTest(k=k), self.assertRaises(ValueError):
                self.store.search((1, 0, 0), k)

    def test_numeric_validation_and_stable_extremes(self):
        invalid = [(1, 2), (0, 0, 0), (math.nan, 0, 1), (math.inf, 1, 0), (-math.inf, 1, 0)]
        for v in invalid:
            with self.subTest(v=v), self.assertRaises(ValueError):
                self.store.add([record("invalid", v)])
            with self.subTest(query=v), self.assertRaises(ValueError):
                self.store.search(v, 1)
        self.store.add([record("huge", (1e308, 1e308, 0)), record("tiny", (5e-324, 5e-324, 0))])
        hits = self.store.search((1e308, 1e308, 0), 2)
        self.assertEqual([x["id"] for x in hits], ["huge", "tiny"])
        for hit in hits:
            self.assertTrue(math.isfinite(hit["score"]))
            self.assertAlmostEqual(hit["score"], 1)

    def test_backup_restore_identity_and_rejection(self):
        self.store.add([record("saved")])
        snapshot = Path(self.tmp.name) / "snapshot.sqlite"
        identity = self.store.backup(snapshot)
        self.assertEqual(identity["sha256"], hashlib.sha256(snapshot.read_bytes()).hexdigest())
        restored = Path(self.tmp.name) / "restored.sqlite"
        Store.restore(snapshot, restored, **identity)
        self.assertEqual(Store(restored).get("saved")["id"], "saved")
        before = restored.read_bytes()
        with self.assertRaises(FileExistsError):
            Store.restore(snapshot, restored, **identity)
        self.assertEqual(before, restored.read_bytes())
        original = snapshot.read_bytes()
        for suffix, content in [("tamper", original[:-1]+bytes([original[-1]^1])), ("short", original[:100]), ("notdb", b"not a sqlite database")]:
            bad = Path(self.tmp.name) / suffix
            bad.write_bytes(content)
            dest = Path(self.tmp.name) / (suffix+".restore")
            with self.assertRaises(ValueError):
                Store.restore(bad, dest, **identity)
            self.assertFalse(dest.exists())
        non = Path(self.tmp.name) / "non-db"
        non.write_bytes(b"not a sqlite database")
        with self.assertRaises(Exception):
            Store.restore(non, Path(self.tmp.name)/"non-result", sha256=hashlib.sha256(non.read_bytes()).hexdigest(), size=non.stat().st_size)
        self.assertFalse((Path(self.tmp.name)/"non-result").exists())
        self.assertEqual(self.store.get("saved")["id"], "saved")

    def test_every_connection_is_hardened(self):
        from store import _connect
        import sqlite3
        for readonly in (False, True):
            con = _connect(self.path, readonly=readonly)
            try:
                self.assertTrue(con.getconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE))
                self.assertFalse(con.getconfig(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA))
                self.assertFalse(con.getconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION))
                self.assertEqual(con.execute("PRAGMA trusted_schema").fetchone()[0], 0)
                self.assertEqual(con.execute("PRAGMA foreign_keys").fetchone()[0], 1)
                self.assertLessEqual(con.getlimit(sqlite3.SQLITE_LIMIT_LENGTH), 1048576)
                self.assertLessEqual(con.getlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH), 65536)
                with self.assertRaises(sqlite3.OperationalError):
                    con.execute("SELECT load_extension('untrusted')")
            finally:
                con.close()

    def test_fixed_schema_dimensions_and_payload_limits(self):
        for dimension in [0, -1, True, 4097, 1.5]:
            with self.subTest(dimension=dimension), self.assertRaises(ValueError):
                Store(Path(self.tmp.name)/"invalid.sqlite", dimension=dimension)
        with self.assertRaises(ValueError):
            Store(self.path, dimension=2)
        for item in [record(1), {**record("x"), "metadata": {"v": math.nan}}, {**record("x"), "text": "x"*1048577}, {**record("x"), "source": 123}]:
            with self.subTest(item_type=type(item["id"]).__name__), self.assertRaises(ValueError):
                self.store.add([record("not-partially-written"), item])
            self.assertIsNone(self.store.get("not-partially-written"))
        with self.assertRaises(ValueError):
            self.store.add([record(str(i)) for i in range(1001)])

    def test_nonfinite_or_invalid_stored_blob_is_rejected(self):
        from store import _connect
        import struct
        self.store.add([record("corrupted")])
        for blob in [struct.pack("<ddd", math.nan, 0, 1), b"bad", bytes(24)]:
            con = _connect(self.path)
            try:
                with con:
                    con.execute("UPDATE records SET vector=? WHERE id=?", (blob,"corrupted"))
            finally:
                con.close()
            with self.subTest(size=len(blob)), self.assertRaises(ValueError):
                self.store.search((1,0,0),1)

    def test_backup_checks_policy_size_before_reading_bytes(self):
        # Policy fault injection, not a mock of SQLite/native IO: make a real
        # backup exceed a tiny budget and observe whether eager bytes were read.
        self.store.add([record("real-backup")])
        snapshot = Path(self.tmp.name)/"too-large.sqlite"
        original = Path.read_bytes
        with patch("store.MAX_SNAPSHOT", 1), patch.object(Path, "read_bytes", autospec=True, side_effect=original) as read:
            with self.assertRaises(ValueError):
                self.store.backup(snapshot)
            self.assertEqual(read.call_count, 0, "backup must reject stat size before allocating bytes")
        self.assertFalse(snapshot.exists())
        self.assertIsNotNone(self.store.get("real-backup"))

    def test_process_readers_writer_lock_timeout_and_abort(self):
        self.store.add([record("base")])
        holder_code = "from store import _connect; import sys,time; c=_connect(sys.argv[1]); c.execute('BEGIN IMMEDIATE'); c.execute(\"INSERT INTO records VALUES ('uncommitted','s','t','{}',?,3)\", (bytes(24),)); print('locked',flush=True); time.sleep(60)"
        holder = subprocess.Popen([sys.executable, "-u", "-c", holder_code, str(self.path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "locked")
            reader_code = "from store import Store; import sys; s=Store(sys.argv[1]); assert s.get('base'); assert s.get('uncommitted') is None; print('reader-ok')"
            readers = [subprocess.Popen([sys.executable,"-c", reader_code,str(self.path)], stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(3)]
            for p in readers:
                out, err = p.communicate(timeout=20)
                self.assertEqual(p.returncode, 0, err)
                self.assertEqual(out.strip(), "reader-ok")
            writer_code = "from store import Store; import sys,sqlite3,time; s=Store(sys.argv[1],timeout=.2); start=time.monotonic();\ntry: s.add([dict(id='blocked',source='s',text='t',metadata={},vector=[1,0,0])])\nexcept sqlite3.OperationalError as e:\n assert 'locked' in str(e); assert .1 < time.monotonic()-start < 10; print('timeout-ok')\nelse: raise AssertionError('expected lock conflict')"
            p = subprocess.run([sys.executable,"-c",writer_code,str(self.path)],capture_output=True,text=True,timeout=20)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertEqual(p.stdout.strip(),"timeout-ok")
        finally:
            holder.terminate()
            holder.communicate(timeout=10)
        self.assertIsNone(Store(self.path).get("uncommitted"))
        self.store.add([record("after-abort")])
        self.assertIsNotNone(Store(self.path).get("after-abort"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
