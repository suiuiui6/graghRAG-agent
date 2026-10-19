import concurrent.futures
import hashlib
import math
from pathlib import Path
import random
import sqlite3
import tempfile
import unittest

from store import Store, _connect


class IndependentTests(unittest.TestCase):
    def test_seeded_reference_and_backup(self):
        rng = random.Random(74101593)
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/'private.sqlite', dimension=7)
            items = []
            evil = "'; DROP TABLE records; -- ? 中国 % _"
            for index in range(137):
                vector = [rng.uniform(-3, 3) for _ in range(7)]
                items.append(dict(id=f'r{index:04}', source=evil if index % 3 == 0 else 'normal',
                                  text=f'正文{index}', metadata={'number': index, 'quote': evil}, vector=vector))
            store.add(items)
            for case in range(13):
                query = [rng.uniform(-5, 5) for _ in range(7)]
                source = evil if case % 2 else None
                expected = []
                for item in items:
                    if source is not None and item['source'] != source:
                        continue
                    value = math.fsum(x*y for x,y in zip(query,item['vector']))
                    value /= math.sqrt(math.fsum(x*x for x in query))*math.sqrt(math.fsum(x*x for x in item['vector']))
                    expected.append((item['id'], (value+1)/2))
                expected.sort(key=lambda pair:(-pair[1], pair[0]))
                actual = store.search(query, 11, source=source)
                self.assertEqual([x['id'] for x in actual], [x[0] for x in expected[:11]])
                for got, wanted in zip(actual, expected):
                    self.assertAlmostEqual(got['score'], wanted[1], places=14)
            snapshot = Path(folder)/'snapshot.sqlite'
            identity = store.backup(snapshot)
            self.assertEqual(identity['sha256'], hashlib.sha256(snapshot.read_bytes()).hexdigest())
            destination = Path(folder)/'restored.sqlite'
            Store.restore(snapshot, destination, **identity)
            restored = Store(destination, dimension=7)
            for item in items:
                result = restored.get(item['id'])
                for key in ('id','source','text','metadata','vector'):
                    self.assertEqual(result[key], item[key])
            store.delete_source(evil)
            self.assertEqual(len(store.search([1]*7, 1000)), 91)
            self.assertEqual(len(restored.search([1]*7, 1000)), 137)

    def test_independent_thread_connections_and_config(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'threads.sqlite'
            Store(path)
            def work(worker):
                store = Store(path, timeout=3)
                for index in range(10):
                    ident = f'{worker}:{index}'
                    store.add([dict(id=ident,source='threads',text='x',metadata={},vector=[1,2,3])])
                    self.assertEqual(store.get(ident)['id'], ident)
                con = _connect(path, readonly=True)
                try:
                    self.assertTrue(con.getconfig(sqlite3.SQLITE_DBCONFIG_DEFENSIVE))
                    self.assertFalse(con.getconfig(sqlite3.SQLITE_DBCONFIG_TRUSTED_SCHEMA))
                    self.assertFalse(con.getconfig(sqlite3.SQLITE_DBCONFIG_ENABLE_LOAD_EXTENSION))
                    self.assertEqual(con.getlimit(sqlite3.SQLITE_LIMIT_ATTACHED), 0)
                    with self.assertRaises(sqlite3.DatabaseError):
                        con.execute("ATTACH DATABASE ':memory:' AS extra")
                finally:
                    con.close()
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(work, range(4)))
            self.assertEqual(len(Store(path).search([1,2,3],1000)),40)


if __name__ == '__main__':
    unittest.main(verbosity=2)
