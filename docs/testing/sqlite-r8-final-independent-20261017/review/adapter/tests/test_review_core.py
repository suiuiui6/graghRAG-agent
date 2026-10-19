import sys, pathlib, sqlite3
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'backend'))
import vector_store as vs
import pytest

def test_invalid_hook_scalar_never_converts(tmp_path):
    class Hook:
        def __float__(self): raise AssertionError('conversion ran')
        def __array__(self,*a): raise AssertionError('array ran')
    s=vs.VectorStore(persist_dir=tmp_path/'db')
    with pytest.raises(vs.VectorInputError):s._collection.add(ids=['x'],embeddings=[[Hook()]])
    assert s.count()==0

def test_mid_transaction_failure_rolls_back_payload_and_dimension(tmp_path,monkeypatch):
    s=vs.VectorStore(persist_dir=tmp_path/'db');original=vs.connect
    class Broken(sqlite3.Connection):
        def execute(self,sql,params=()):
            if sql=='INSERT INTO payload VALUES (?,?,?,?)':raise sqlite3.OperationalError('disk full injected')
            return super().execute(sql,params)
    def connect(path,ro=False):
        if pathlib.Path(path)==s.path and not ro:
            c=sqlite3.connect(path,factory=Broken);c.execute('PRAGMA foreign_keys=ON');return c
        return original(path,ro)
    monkeypatch.setattr(vs,'connect',connect)
    with pytest.raises(vs.VectorStorageError):s._collection.add(ids=['x'],embeddings=[[1.,0.]],documents=['text'])
    with original(s.path,True) as c:
        assert c.execute('SELECT count(*) FROM records').fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM payload').fetchone()[0]==0
        assert c.execute('SELECT dimension FROM collections').fetchone()[0] is None
    assert not list((tmp_path/'db').glob('tmp*'))

def test_restore_hash_mismatch_does_not_parse_or_create_target(tmp_path,monkeypatch):
    snapshot=tmp_path/'bad';snapshot.write_bytes(b'not sqlite')
    def no_parse(*a,**kw):raise AssertionError('parsed before trusted hash')
    monkeypatch.setattr(vs,'connect',no_parse)
    with pytest.raises(vs.VectorInputError):vs.VectorStore.restore(snapshot,tmp_path/'target',sha256='0'*64,size=10)
    assert not (tmp_path/'target').exists()

def test_backup_restore_and_collection_name_cannot_traverse(tmp_path):
    s=vs.VectorStore(collection_name='../escape',persist_dir=tmp_path/'db')
    s._collection.add(ids=['x'],embeddings=[[1.,0.]],documents=['汉字'])
    receipt=s.backup(tmp_path/'backup')
    r=vs.VectorStore.restore(tmp_path/'backup',tmp_path/'restored',collection_name='../escape',**receipt)
    assert r.get_by_ids(['x'])[0]['text']=='汉字'
    assert not (tmp_path/'escape').exists()
def test_restore_rejects_wrong_payload_schema(tmp_path):
    import hashlib
    p=tmp_path/'malformed.sqlite'
    with sqlite3.connect(p) as c:
        c.execute('CREATE TABLE collections(name TEXT PRIMARY KEY,dimension INTEGER)')
        c.execute('CREATE TABLE records(seq INTEGER PRIMARY KEY,collection TEXT,id TEXT)')
        c.execute('CREATE TABLE payload(arbitrary TEXT)')
    data=p.read_bytes()
    with pytest.raises(vs.VectorInputError):
        vs.VectorStore.restore(p,tmp_path/'bad-restored',sha256=hashlib.sha256(data).hexdigest(),size=len(data))
