import hashlib
import json
import pathlib
import sqlite3
import subprocess
import sys
import time
import numpy as np

root=pathlib.Path(__file__).resolve().parent
run_id=time.time_ns()
path=root/f'reference-{run_id}.sqlite3'
backup=root/f'reference-backup-{run_id}.sqlite3'
db=sqlite3.connect(path)
db.execute('CREATE TABLE chunks (id TEXT PRIMARY KEY, source TEXT NOT NULL, text TEXT NOT NULL, metadata_json TEXT NOT NULL, vector BLOB NOT NULL, dim INTEGER NOT NULL)')
metadata={'source_file':"x' OR 1=1 --",'page_idx':1,'active':True,'weight':1.25,'entity_ids':['实体',None],'nested':{'a':2}}
v=np.array([1.,0.,0.],dtype='<f4')
with db:
    db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)',('a',metadata['source_file'],'合成文本',json.dumps(metadata,ensure_ascii=False),v.tobytes(),3))
row=db.execute('SELECT id,metadata_json,vector,dim FROM chunks WHERE source=?',(metadata['source_file'],)).fetchone()
assert row[0]=='a' and json.loads(row[1])==metadata
assert np.array_equal(np.frombuffer(row[2],dtype='<f4'),v)
assert db.execute('SELECT count(*) FROM chunks WHERE source=?',("' OR 1=1 --",)).fetchone()[0]==0
try:
    with db:
        db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)',('b','s','x','{}',v.tobytes(),3))
        db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)',('a','s','x','{}',v.tobytes(),3))
except sqlite3.IntegrityError:
    pass
else:
    raise AssertionError('primary key did not reject duplicate')
assert db.execute('SELECT count(*) FROM chunks').fetchone()[0]==1
out=sqlite3.connect(backup)
db.backup(out); out.close()
with db:
    db.execute('DELETE FROM chunks WHERE id=?',('a',))
assert db.execute('SELECT count(*) FROM chunks').fetchone()[0]==0
src=sqlite3.connect(backup); src.backup(db); src.close()
assert db.execute('SELECT count(*) FROM chunks').fetchone()[0]==1
db.close()
p=subprocess.run([sys.executable,'-c',"import sqlite3; d=sqlite3.connect("+repr(str(path))+"); print(d.execute('SELECT count(*) FROM chunks').fetchone()[0])"],capture_output=True,text=True,timeout=30)
assert p.returncode==0 and p.stdout.strip()=='1'
rng=np.random.default_rng(20261013); vectors=rng.normal(size=(5000,512)).astype('<f4')
db=sqlite3.connect(path)
start=time.perf_counter()
with db:
    db.executemany('INSERT INTO chunks VALUES(?,?,?,?,?,?)',((f'scale-{i}',f's-{i%10}','规模文本','{}',vector.tobytes(),512) for i,vector in enumerate(vectors)))
write_seconds=time.perf_counter()-start
start=time.perf_counter(); fetched=db.execute('SELECT id,vector FROM chunks WHERE dim=?',(512,)).fetchall(); load_seconds=time.perf_counter()-start
matrix=np.stack([np.frombuffer(x[1],dtype='<f4') for x in fetched]); normalized=matrix/np.linalg.norm(matrix,axis=1,keepdims=True)
times=[]
for i in range(30):
    start=time.perf_counter(); similarities=normalized@(vectors[i]/np.linalg.norm(vectors[i])); order=np.argsort(-similarities,kind='stable')[:10]; times.append(time.perf_counter()-start)
    assert fetched[int(order[0])][0]==f'scale-{i}'
result={'status':'PASS','sqlite_version':sqlite3.sqlite_version,'numpy_version':np.__version__,'checks':['parameter_binding','metadata_type_fidelity','vector_blob_fidelity','duplicate_primary_key','transaction_rollback','backup_clear_restore','child_process_reopen','exact_cosine_5000x512'],'rows':5000,'dimensions':512,'write_seconds':write_seconds,'read_blob_seconds':load_seconds,'warm_query_ms_p50':float(np.percentile(times,50)*1000),'warm_query_ms_p95':float(np.percentile(times,95)*1000),'boundaries':['full_adapter_not_implemented','cross_process_cache_invalidation_not_run','parallel_process_writes_not_run','kill_power_loss_not_run'],'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
(root/f'sqlite-results-{time.time_ns()}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
