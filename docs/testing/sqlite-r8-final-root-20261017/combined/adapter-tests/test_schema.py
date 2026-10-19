import sys,unittest,hashlib
from pathlib import Path
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import vector_store as vs
from sqlite_vector_payload import temporary_directory

class Schema(unittest.TestCase):
    def test_wrong_payload_rejected_restore_and_reopen(self):
        with temporary_directory(dir=Path(__file__).resolve().parents[1]) as d:
            s=vs.VectorStore(persist_dir=d)
            with closing(vs.connect(s.path)) as c,c:
                c.execute('DROP TABLE payload');c.execute('CREATE TABLE payload(arbitrary TEXT)')
            raw=s.path.read_bytes()
            identity={'sha256':hashlib.sha256(raw).hexdigest(),'size':len(raw)}
            target=Path(d)/'restored'
            with self.assertRaises(vs.VectorInputError):vs.VectorStore.restore(s.path,target,**identity)
            self.assertFalse(target.exists())
            with self.assertRaises(vs.VectorInputError):vs.VectorStore(persist_dir=d)
            self.assertEqual(s.path.read_bytes(),raw)

    def test_extra_trigger_rejected(self):
        with temporary_directory(dir=Path(__file__).resolve().parents[1]) as d:
            s=vs.VectorStore(persist_dir=d)
            with closing(vs.connect(s.path)) as c,c:c.execute('CREATE TRIGGER extra AFTER INSERT ON records BEGIN DELETE FROM records; END')
            with self.assertRaises(vs.VectorInputError):vs.VectorStore(persist_dir=d)

if __name__=='__main__':unittest.main()
